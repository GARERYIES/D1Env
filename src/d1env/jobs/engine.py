"""One worker per target, with persistent idempotency and POSIX ownership locks."""

import fcntl
import os
import stat
import threading
import time
from pathlib import Path

from pydantic import ValidationError

from d1env.jobs.mock import MOCK_OPERATION_IDS, MockExecutor
from d1env.jobs.store import TERMINAL_STATES, JobConflict, Store
from d1env.models import (
    DeploymentPlan,
    ExecutionContext,
    JobEvent,
    JobSnapshot,
    JobState,
    JSONValue,
)

OPERATION_STATES: dict[str, JobState] = {
    "preflight": "PREFLIGHT",
    "acquire": "ACQUIRING",
    "configure": "CONFIGURING",
    "start": "STARTING",
    "verify": "VERIFYING",
    "verify_failure": "VERIFYING",
}


class InvalidPlan(ValueError):
    code = "INVALID_MOCK_PLAN"


class _TargetLock:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fd: int | None = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def release(self) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


class JobEngine:
    def __init__(self, store: Store, work_dir: Path, executor: MockExecutor | None = None):
        if executor is not None and not isinstance(executor, MockExecutor):
            raise TypeError("this stage only enables MockExecutor")
        self.store = store
        self.work_dir = Path(work_dir).resolve()
        self.executor = executor or MockExecutor()

    def _lock_path(self, target_id: str) -> Path:
        if target_id != "local":
            raise InvalidPlan("本轮仅允许登记的 local 目标。")
        return self.store.path.parent / "locks" / f"{target_id}.lock"

    @staticmethod
    def _validate_plan(plan: DeploymentPlan) -> DeploymentPlan:
        try:
            validated = DeploymentPlan.model_validate(plan.model_dump())
        except ValidationError as error:
            raise InvalidPlan("计划校验失败；请重新预览 MOCK 计划。") from error
        ids = [operation.operation_id for operation in validated.operations]
        if (
            validated.mode != "mock"
            or not ids
            or any(step not in MOCK_OPERATION_IDS for step in ids)
        ):
            raise InvalidPlan("执行被阻止：本轮只实现白名单 MOCK 步骤；请选择演示计划。")
        valid_order = ids in (
            ["preflight", "acquire", "configure", "start", "verify"],
            ["preflight", "acquire", "configure", "start", "verify_failure"],
        )
        if (
            not valid_order
            or any(not operation.reversible for operation in validated.operations)
            or "mock_ready" not in validated.required_evidence
        ):
            raise InvalidPlan("计划步骤顺序、可撤销范围或 MOCK 就绪证据不完整；请重新预览。")
        return validated

    def submit(self, plan: DeploymentPlan, idempotency_key: str) -> JobSnapshot:
        plan = self._validate_plan(plan)
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or len(idempotency_key) > 128
            or any(ord(char) < 32 for char in idempotency_key)
        ):
            raise InvalidPlan("请求键校验失败；请使用 1–128 个可显示字符的新请求键。")
        lease: _TargetLock | None = None

        def acquire() -> None:
            nonlocal lease
            try:
                lease = _TargetLock(self._lock_path(plan.target_id))
            except BlockingIOError as error:
                raise JobConflict(
                    "TARGET_LOCKED",
                    "目标锁被另一进程占用；检测证据：POSIX 锁忙；等待其结束后重试。",
                ) from error

        try:
            job, created = self.store.claim(plan, idempotency_key, acquire)
            if created:
                assert lease is not None
                worker = threading.Thread(
                    target=self._run,
                    args=(job, plan, lease),
                    daemon=True,
                    name=f"d1env-mock-{job.job_id}",
                )
                try:
                    worker.start()
                except RuntimeError as error:
                    self.store.transition(
                        job.job_id,
                        "INTERRUPTED",
                        "MOCK 后台步骤未能启动；检测证据：本地线程启动失败；请检查系统资源并使用新请求键重试。",
                        error_code="WORKER_START_FAILED",
                        evidence={"exception_type": type(error).__name__},
                        release_lock=lease.release,
                    )
                    raise JobConflict(
                        "WORKER_START_FAILED",
                        "MOCK 后台步骤未能启动；已记录中断，检查系统资源后用新请求键重试。",
                    ) from error
            return job
        except BaseException:
            if lease is not None:
                lease.release()
            raise

    def get(self, job_id: str) -> JobSnapshot:
        return self.store.get_job(job_id)

    def get_events(self, job_id: str) -> list[JobEvent]:
        return self.store.get_events(job_id)

    def cancel(self, job_id: str) -> JobSnapshot:
        return self.store.request_cancel(job_id)

    def _cleanup(self, job_id: str) -> None:
        removed: list[JSONValue] = []
        preserved: list[JSONValue] = []
        directory = self.work_dir / job_id
        try:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            descriptor = None
        try:
            for resource in self.store.resources(job_id):
                name = str(resource["resource_id"])
                if resource["cleaned"]:
                    continue
                if descriptor is None or Path(name).name != name or not name.endswith(".mock"):
                    preserved.append(name)
                    continue
                try:
                    observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if (
                        not stat.S_ISREG(observed.st_mode)
                        or observed.st_ino != resource["inode"]
                        or observed.st_dev != resource["device"]
                    ):
                        preserved.append(name)
                        continue
                    os.unlink(name, dir_fd=descriptor)
                    self.store.resource_cleaned(job_id, name)
                    removed.append(name)
                except FileNotFoundError:
                    self.store.resource_cleaned(job_id, name)
                except OSError:
                    preserved.append(name)
        finally:
            if descriptor is not None:
                os.close(descriptor)
        self.store.append_event(
            job_id,
            "cleanup",
            "MOCK 取消清理完成；仅撤销本作业登记且归属匹配的资源。",
            {"removed_resources": removed, "preserved_resources": preserved},
        )
        try:
            directory.rmdir()  # Only an empty directory is removable; user map/bag files remain.
        except OSError:
            pass

    def _cancel_worker(self, job_id: str, lease: _TargetLock) -> None:
        self._cleanup(job_id)
        self.store.transition(
            job_id,
            "CANCELLED",
            "MOCK 作业已取消；此状态不代表硬件急停。",
            release_lock=lease.release,
        )

    def _run(self, job: JobSnapshot, plan: DeploymentPlan, lease: _TargetLock) -> None:
        evidence: dict[str, JSONValue] = {}
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            directory = self.work_dir / job.job_id
            directory.mkdir(exist_ok=False)

            def emit(event: JobEvent) -> None:
                if event.job_id != job.job_id or event.mode != "mock" or event.origin != "mock":
                    raise ValueError("event is outside this MOCK job")
                self.store.append_event(
                    job.job_id, event.event_type, event.message, event.evidence, event.operation_id
                )

            context = ExecutionContext(
                job_id=job.job_id,
                target_id=job.target_id,
                mode="mock",
                work_dir=directory,
                is_cancelled=lambda: self.store.is_cancelled(job.job_id),
                emit=emit,
            )
            for operation in plan.operations:
                if context.is_cancelled():
                    self._cancel_worker(job.job_id, lease)
                    return
                self.store.transition(
                    job.job_id,
                    OPERATION_STATES[operation.operation_id],
                    f"MOCK 正在执行：{operation.label}。",
                    operation_id=operation.operation_id,
                )
                self.store.append_event(
                    job.job_id,
                    "operation_started",
                    f"MOCK 开始：{operation.label}。",
                    operation_id=operation.operation_id,
                )
                started = time.monotonic()
                result = self.executor.execute(operation, context)
                for name in result.resource_ids:
                    if Path(name).name != name or not name.endswith(".mock"):
                        raise ValueError("unowned MOCK resource path rejected")
                    metadata = (directory / name).lstat()
                    if not stat.S_ISREG(metadata.st_mode):
                        raise ValueError("MOCK resource must be a regular file")
                    self.store.register_resource(job.job_id, name, metadata.st_dev, metadata.st_ino)
                if result.operation_id != operation.operation_id or result.origin != "mock":
                    raise ValueError("operation returned mismatched evidence")
                if context.is_cancelled() or result.status == "cancelled":
                    self._cancel_worker(job.job_id, lease)
                    return
                if (
                    time.monotonic() - started > operation.timeout_s
                    and result.status == "succeeded"
                ):
                    result = result.model_copy(
                        update={
                            "status": "failed",
                            "error_code": "OPERATION_TIMEOUT",
                            "message": "MOCK 步骤超时；检测证据：软件计时超过步骤期限；请检查步骤设置后重试。",
                        }
                    )
                missing: list[JSONValue] = [
                    key
                    for key in operation.required_evidence
                    if result.evidence.get(key) is not True
                ]
                if result.status == "failed" or missing:
                    code = result.error_code or "OPERATION_EVIDENCE_MISSING"
                    details: dict[str, JSONValue] = {
                        **result.evidence,
                        "error_code": code,
                        "missing_evidence": missing,
                    }
                    self.store.append_event(
                        job.job_id,
                        "operation_failed",
                        result.message,
                        details,
                        operation.operation_id,
                    )
                    self.store.transition(
                        job.job_id,
                        "FAILED",
                        result.message,
                        error_code=code,
                        operation_id=operation.operation_id,
                        release_lock=lease.release,
                    )
                    return
                evidence.update(result.evidence)
                self.store.append_event(
                    job.job_id,
                    "operation_succeeded",
                    result.message,
                    result.evidence,
                    operation.operation_id,
                )
            missing = [key for key in plan.required_evidence if evidence.get(key) is not True]
            if missing:
                self.store.transition(
                    job.job_id,
                    "FAILED",
                    "MOCK 就绪验证失败；检测证据：所需证据缺失；请重新预览并检查步骤后重试。",
                    error_code="READINESS_EVIDENCE_MISSING",
                    evidence={"missing_evidence": missing},
                    release_lock=lease.release,
                )
                return
            completed = self.store.transition(
                job.job_id,
                "SUCCEEDED",
                "演示流程完成（MOCK），未部署真机。",
                evidence=evidence,
                release_lock=lease.release,
            )
            if completed.state != "SUCCEEDED":
                self._cancel_worker(job.job_id, lease)
        except Exception as error:  # noqa: BLE001 - worker boundary must persist an honest failure
            if self.store.is_cancelled(job.job_id):
                self._cancel_worker(job.job_id, lease)
            else:
                self.store.transition(
                    job.job_id,
                    "FAILED",
                    "MOCK 执行失败；检测证据：本地演示步骤异常；请导出诊断并使用新请求键重试。",
                    error_code="MOCK_EXECUTION_ERROR",
                    evidence={"exception_type": type(error).__name__},
                    release_lock=lease.release,
                )
        finally:
            lease.release()

    def reconcile_on_startup(self) -> list[JobSnapshot]:
        unfinished = [job for job in self.store.list_jobs() if job.state not in TERMINAL_STATES]
        changed: list[JobSnapshot] = []
        for target in {job.target_id for job in unfinished}:
            try:
                lease = _TargetLock(self._lock_path(target))
            except BlockingIOError:
                continue  # Another process owns a live worker: it must not become INTERRUPTED.
            try:
                for job in unfinished:
                    if job.target_id != target or self.get(job.job_id).state in TERMINAL_STATES:
                        continue
                    resources = self.store.resources(job.job_id)
                    inventory: list[JSONValue] = []
                    for resource in resources:
                        path = self.work_dir / job.job_id / str(resource["resource_id"])
                        inventory.append(
                            {**resource, "present": path.is_file() and not path.is_symlink()}
                        )
                    self.store.append_event(
                        job.job_id,
                        "inventory",
                        "MOCK 服务重启资源盘点；未重启步骤或删除用户数据。",
                        {"resources": inventory, "auto_restart": False},
                    )
                    changed.append(
                        self.store.transition(
                            job.job_id,
                            "INTERRUPTED",
                            "MOCK 作业中断；检测证据：数据库非终态且没有活动目标锁；请核对盘点后用新请求键重试。",
                            error_code="WORKER_INTERRUPTED",
                        )
                    )
            finally:
                lease.release()
        return changed
