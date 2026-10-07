"""Persistent, single-target first-run tasks; reads never install or start services."""

import fcntl
import json
import os
import platform as host_platform
import stat
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, ValidationError

from d1env.models import JSONValue, StrictModel, utcnow
from d1env.runtime import ensure_private_state_dir

from .download import InstallerDownloader
from .installer import MacInstaller
from .models import (
    REQUEST_KEY,
    TASK_ID,
    SetupAction,
    SetupError,
    SetupStage,
    SetupState,
    SetupTask,
    validate_descriptor,
    validate_installer_lock,
    validate_private_file,
)


class Downloader(Protocol):
    def fetch(self, lock: dict[str, JSONValue], cancel: threading.Event,
              progress: Callable[[int, int], None]) -> Path: ...


class NativeInstaller(Protocol):
    def app_exists(self) -> bool: ...
    def install(self, dmg: Path, lock: dict[str, JSONValue], task_id: str,
                cancel: threading.Event) -> dict[str, JSONValue]: ...
    def start(self, lock: dict[str, JSONValue], cancel: threading.Event) -> dict[str, JSONValue]: ...


class _Index(StrictModel):
    schema_version: Literal[1] = 1
    latest_task_id: str | None = None
    tasks: dict[str, SetupTask] = Field(default_factory=dict)


class _Lease:
    def __init__(self, path: Path):
        validate_private_file(path, missing_ok=True)
        self.fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            validate_descriptor(self.fd)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd)
            raise

    def close(self) -> None:
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


class SetupManager:
    def __init__(self, state_dir: Path, *, installer_lock: dict[str, JSONValue],
                 probe: Callable[[], dict[str, JSONValue]],
                 prepare_image: Callable[[Callable[[], bool]], dict[str, JSONValue]],
                 image_probe: Callable[[], dict[str, JSONValue]] | None = None,
                 platform: dict[str, JSONValue] | None = None,
                 downloader: Downloader | None = None, native: NativeInstaller | None = None,
                 wait_timeout_s: float = 90, wait_interval_s: float = 2):
        root = ensure_private_state_dir(state_dir.absolute())
        self.directory = ensure_private_state_dir(root / "runtime-setup")
        self.state_path = self.directory / "tasks.json"
        self.lease_path = self.directory / "target.lock"
        self.cancel_dir = ensure_private_state_dir(self.directory / "cancellations")
        self.cache_dir = ensure_private_state_dir(self.directory / "cache")
        self.installer_lock = installer_lock
        self.probe = probe
        self.prepare_image = prepare_image
        self.image_probe = image_probe or (lambda: {"artifact_ready": None, "reason": "no_readonly_image_probe"})
        self.platform = platform or {
            "os_name": host_platform.system(),
            "architecture": {"arm64": "aarch64", "AMD64": "x86_64"}.get(host_platform.machine(), host_platform.machine()),
            "os_version": host_platform.mac_ver()[0] or host_platform.release(),
        }
        if not 0 < wait_timeout_s <= 120 or not 0 < wait_interval_s <= 5:
            raise ValueError("bounded runtime readiness wait required")
        self.wait_timeout_s = wait_timeout_s
        self.wait_interval_s = wait_interval_s
        self.downloader = downloader or InstallerDownloader(self.cache_dir)
        self.native = native or MacInstaller(self.cache_dir)
        self._mutex = threading.RLock()
        self._cancel_events: dict[str, threading.Event] = {}
        try:
            lease = self._acquire()
        except SetupError as exc:
            if exc.code != "SETUP_BUSY":
                raise
            self._read()  # A live worker elsewhere is never marked interrupted.
        else:
            try:
                index = self._read() if self.state_path.exists() or self.state_path.is_symlink() else _Index()
                for task in index.tasks.values():
                    cancellation = self.cancel_dir / f"{task.task_id}.cancel"
                    if task.state in {"RUNNING", "WAITING_USER"} and (cancellation.exists() or cancellation.is_symlink()):
                        validate_private_file(cancellation)
                        self._change(task, "CANCELLED", task.stage, "已恢复上次明确的取消请求，保留已有环境")
                    elif task.state == "RUNNING":
                        self._change(task, "INTERRUPTED", task.stage, "准备进程已中断，未自动继续安装或启动",
                                     remediation="检查系统原生窗口及现有运行环境，再明确创建新准备任务",
                                     error={"code": "SETUP_INTERRUPTED", "message": "上次准备任务没有完成"})
                self._write(index)
            finally:
                lease.close()

    def _directory_check(self) -> None:
        ensure_private_state_dir(self.directory)
        if self.directory.lstat().st_mode & 0o077:
            raise SetupError("SETUP_DIRECTORY_UNSAFE", "首次准备目录必须为用户私有目录",
                             "检查状态目录归属与权限，不使用共享目录")

    def _acquire(self) -> _Lease:
        self._directory_check()
        try:
            return _Lease(self.lease_path)
        except BlockingIOError as exc:
            raise SetupError("SETUP_BUSY", "本机已有运行环境准备任务", "等待当前任务完成，或返回当前任务取消") from exc
        except OSError as exc:
            raise SetupError("SETUP_FILE_UNSAFE", "准备锁文件无法安全打开", "检查私有状态目录，不放宽文件权限") from exc

    def _read(self) -> _Index:
        for _ in range(3):
            descriptor: int | None = None
            try:
                self._directory_check()
                validate_private_file(self.state_path)
                descriptor = os.open(self.state_path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    validate_descriptor(descriptor)
                except SetupError:
                    opened = os.fstat(descriptor)
                    # A normal owned os.replace can unlink the already-open old inode.
                    # Never accept that descriptor: only reopen a different fully safe current file.
                    if (opened.st_nlink == 0 and stat.S_ISREG(opened.st_mode)
                            and opened.st_uid == os.getuid() and not opened.st_mode & 0o077):
                        self._directory_check()
                        validate_private_file(self.state_path)
                        current = self.state_path.lstat()
                        if (stat.S_ISREG(current.st_mode) and current.st_uid == os.getuid()
                                and current.st_nlink == 1 and not current.st_mode & 0o077
                                and (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)):
                            continue
                    raise
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    raw = stream.read(2 * 1024**2 + 1)
                if len(raw) > 2 * 1024**2:
                    raise ValueError("state too large")
                index = _Index.model_validate(json.loads(raw))
                if len(index.tasks) > 200 or any(key != task.task_id for key, task in index.tasks.items()):
                    raise ValueError("state identities inconsistent")
                if index.latest_task_id is not None and index.latest_task_id not in index.tasks:
                    raise ValueError("latest task unknown")
                return index
            except (ValueError, ValidationError, OSError) as exc:
                raise SetupError("SETUP_STATE_INVALID", "首次准备持久状态无法校验",
                                 "保留现有文件以排查；不要把未知任务当作完成") from exc
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        raise SetupError("SETUP_STATE_INVALID", "首次准备状态正在并发替换，有限重读未取得可信快照",
                         "当前状态保持未知，请稍后重新检查；不会沿用旧任务成功状态",
                         {"reason": "atomic_state_replacements_exhausted", "max_attempts": 3})

    def _write(self, index: _Index) -> None:
        self._directory_check()
        validate_private_file(self.state_path, missing_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".tasks-", dir=self.directory)
        temporary = Path(name)
        try:
            validate_descriptor(descriptor)
            raw = index.model_dump_json().encode("utf-8")
            if len(raw) > 2 * 1024**2:
                raise SetupError("SETUP_HISTORY_FULL", "准备任务历史达到存储上限", "保留诊断文件后使用新的用户私有状态目录")
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(descriptor)
            validate_private_file(self.state_path, missing_ok=True)
            os.replace(temporary, self.state_path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.close(descriptor)
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _change(task: SetupTask, state: SetupState, stage: SetupStage, message: str, *,
                remediation: str = "", user_action: SetupAction | None = None,
                evidence: dict[str, JSONValue] | None = None,
                error: dict[str, JSONValue] | None = None) -> None:
        task.state, task.stage, task.message = state, stage, message
        task.remediation, task.user_action, task.error = remediation, user_action, error
        code = error.get("code") if error else None
        task.error_code = code if isinstance(code, str) else None
        task.updated_at = utcnow().isoformat()
        task.environment_ready = None
        if evidence:
            task.evidence[stage] = evidence
        task.events.append({"scope": "runtime_environment", "state": state, "stage": stage,
                            "message": message, "observed_at": task.updated_at,
                            "evidence": evidence or {}})
        task.events = task.events[-64:]

    @staticmethod
    def _docker_ready(host: dict[str, JSONValue]) -> bool | None:
        if host.get("docker_accessible") is False:
            return False
        if host.get("endpoint_local") is False:
            return False
        if host.get("docker_accessible") is not True or host.get("endpoint_local") is not True:
            return None
        if host.get("docker_available") is not True:
            return None
        if host.get("docker_os") != "linux" or host.get("docker_architecture") != "aarch64":
            return False if host.get("docker_os") and host.get("docker_architecture") else None
        if host.get("compose_available") is not True:
            return False if host.get("compose_available") is False else None
        return True

    def _current(self) -> tuple[bool | None, dict[str, JSONValue], dict[str, JSONValue]]:
        try:
            host = self.probe()
        except Exception as exc:  # noqa: BLE001 - failed injected/native observations must remain UNKNOWN.
            return None, {"error": "probe_failed", "exception_type": type(exc).__name__}, {}
        if not isinstance(host, dict):
            return None, {"error": "probe_malformed"}, {}
        if not self._platform_supported():
            return None, host, {"artifact_ready": None, "reason": "runtime_platform_not_supported"}
        docker = self._docker_ready(host)
        if docker is not True:
            return docker, host, {}
        try:
            artifact = self.image_probe()
        except Exception as exc:  # noqa: BLE001 - an image probe error cannot inherit historical success.
            return None, host, {"artifact_ready": None, "exception_type": type(exc).__name__}
        if not isinstance(artifact, dict):
            return None, host, {"artifact_ready": None, "error": "image_probe_malformed"}
        image = artifact.get("artifact_ready")
        return (True if image is True else False if image is False else None), host, artifact

    def _view(self, task: SetupTask, current: tuple[bool | None, dict[str, JSONValue], dict[str, JSONValue]] | None = None) -> dict[str, JSONValue]:
        ready, host, image = current if current is not None else self._current()
        result: dict[str, JSONValue] = task.model_dump(mode="json")
        result["environment_ready"] = ready
        result["current_evidence"] = {"host": host, "artifact": image, "observed_at": utcnow().isoformat()}
        return result

    def status(self) -> dict[str, JSONValue]:
        index = self._read()
        current = self._current()
        task = index.tasks.get(index.latest_task_id or "")
        lock_keys = ("version", "build", "url", "sha256", "size_bytes", "license_url", "platform", "architecture")
        try:
            validate_installer_lock(self.installer_lock)
            installer: dict[str, JSONValue] = {key: self.installer_lock.get(key) for key in lock_keys}
            installer["source_status"] = "verified"
            installer["blocked_reason"] = None
        except SetupError as exc:
            installer = {key: None for key in lock_keys}
            installer.update({"source_status": "blocked", "reason": exc.message, "blocked_reason": exc.message})
        return {"scope": "runtime_environment", "environment_ready": current[0], "host": current[1],
                "artifact": current[2], "evidence": {"host": current[1], "artifact": current[2]}, "task": self._view(task, current) if task else None,
                "installer": installer, "platform": {
                    "os": self.platform.get("os_name"), "architecture": self.platform.get("architecture"),
                    "version": self.platform.get("os_version"), "supported": self._platform_supported(),
                }, "observed_at": utcnow().isoformat(),
                "message": "此平台未支持本轮自动环境准备" if not self._platform_supported() else "当前软件运行环境已取得（不代表 ROS 通信或 D1 就绪）" if current[0] is True else "运行环境尚未就绪或状态未知",
                "remediation": "当前候选仅支持 Mac Apple Silicon；Linux、Intel Mac 和旧系统尚未验收，MOCK 可继续" if not self._platform_supported() else "点击准备运行环境；系统许可与授权仍由你在原生窗口完成"}

    def _get_task(self, index: _Index, task_id: str) -> SetupTask:
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise SetupError("SETUP_TASK_ID_INVALID", "准备任务 ID 不合法", "选择本机已有准备任务")
        task = index.tasks.get(task_id)
        if task is None:
            raise SetupError("SETUP_TASK_NOT_FOUND", "未找到本机准备任务", "返回执行电脑页重新检查")
        return task

    def get(self, task_id: str) -> dict[str, JSONValue]:
        return self._view(self._get_task(self._read(), task_id))

    def prepare(self, request_key: str) -> dict[str, JSONValue]:
        if not isinstance(request_key, str) or not REQUEST_KEY.fullmatch(request_key):
            raise SetupError("SETUP_REQUEST_INVALID", "准备请求标识不合法", "使用界面生成的请求，不提供路径或命令")
        with self._mutex:
            existing = self._read()
            previous = next((task for task in existing.tasks.values() if task.request_key == request_key), None)
            if previous:
                return self._view(previous)
            try:
                lease = self._acquire()
            except SetupError as exc:
                if exc.code == "SETUP_BUSY":
                    raced = self._read()
                    previous = next((task for task in raced.tasks.values() if task.request_key == request_key), None)
                    if previous:
                        return self._view(previous)
                raise
            launched = False
            try:
                index = self._read()
                previous = next((task for task in index.tasks.values() if task.request_key == request_key), None)
                if previous:
                    return self._view(previous)
                if any(task.state in {"RUNNING", "WAITING_USER"} for task in index.tasks.values()):
                    raise SetupError("SETUP_BUSY", "本机已有待完成的运行环境准备任务", "继续或取消当前任务后再创建新任务")
                if len(index.tasks) >= 200:
                    raise SetupError("SETUP_HISTORY_FULL", "准备历史达到存储上限", "保留诊断后使用新的用户私有状态目录")
                now = utcnow().isoformat()
                task = SetupTask(task_id=uuid.uuid4().hex, request_key=request_key,
                                 message="正在检测本机运行环境", created_at=now, updated_at=now)
                index.tasks[task.task_id] = task
                index.latest_task_id = task.task_id
                self._write(index)
                self._launch(task.task_id, lease)
                launched = True
            finally:
                if not launched:
                    lease.close()
        return self.get(task.task_id)

    def continue_task(self, task_id: str, action: str = "check_again") -> dict[str, JSONValue]:
        with self._mutex:
            lease = self._acquire()
            try:
                index = self._read()
                task = self._get_task(index, task_id)
                if task.state != "WAITING_USER" or action != task.user_action or action not in {"accept_license", "check_again"}:
                    raise SetupError("SETUP_ACTION_INVALID", "当前任务不接受此继续操作", "按任务显示的许可确认或重新检查按钮操作")
                if action == "accept_license":
                    task.license_accepted = True
                self._change(task, "RUNNING", task.stage, "正在继续运行环境准备")
                self._write(index)
                self._launch(task_id, lease)
            except BaseException:
                lease.close()
                raise
        return self.get(task_id)

    def _finish_cancel(self, task_id: str) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with self._mutex:
                    lease = self._acquire()
                    try:
                        index = self._read()
                        task = self._get_task(index, task_id)
                        if task.state in {"RUNNING", "WAITING_USER"}:
                            self._check_cancel(task_id, threading.Event())
                    except SetupError as exc:
                        if exc.code != "SETUP_CANCELLED":
                            raise
                        self._change(task, "CANCELLED", task.stage, "已取消环境准备，保留已有 Docker 与镜像")
                        self._write(index)
                    finally:
                        lease.close()
                return
            except SetupError as exc:
                if exc.code != "SETUP_BUSY":
                    return
            except OSError:
                return
            time.sleep(0.01)

    def cancel(self, task_id: str) -> dict[str, JSONValue]:
        with self._mutex:
            task = self._get_task(self._read(), task_id)
            if task.state in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"}:
                return self._view(task)
            path = self.cancel_dir / f"{task_id}.cancel"
            ensure_private_state_dir(self.cancel_dir)
            validate_private_file(path, missing_ok=True)
            descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                validate_descriptor(descriptor)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            event = self._cancel_events.get(task_id)
            if event:
                event.set()
            if task.state == "WAITING_USER":
                try:
                    lease = self._acquire()
                except SetupError as exc:
                    if exc.code != "SETUP_BUSY":
                        raise
                    # The waiting transition may precede worker lease release.
                    # Marker + worker finalization cover this process; a bounded
                    # handoff also handles a worker in another process.
                    threading.Thread(target=self._finish_cancel, args=(task_id,), daemon=True).start()
                    result = self._view(task)
                    result["message"] = "取消请求已记录，正在结束本次准备任务"
                    return result
                try:
                    index = self._read()
                    task = self._get_task(index, task_id)
                    self._change(task, "CANCELLED", task.stage, "已取消环境准备，保留已有 Docker 与镜像",
                                 remediation="可显式创建新的准备任务；不会卸载或停止已有服务")
                    self._write(index)
                finally:
                    lease.close()
                return self._view(task)
        result = self.get(task_id)
        result["message"] = "取消请求已记录，正在结束本任务步骤；不会停止或卸载已有 Docker"
        return result

    def _launch(self, task_id: str, lease: _Lease) -> None:
        event = threading.Event()
        self._cancel_events[task_id] = event
        threading.Thread(target=self._worker, args=(task_id, lease, event), daemon=True,
                         name=f"d1env-runtime-{task_id[:8]}").start()

    def _update(self, task_id: str, state: SetupState, stage: SetupStage, message: str, *,
                remediation: str = "", user_action: SetupAction | None = None,
                evidence: dict[str, JSONValue] | None = None, error: dict[str, JSONValue] | None = None) -> SetupTask:
        with self._mutex:
            index = self._read()
            task = self._get_task(index, task_id)
            self._change(task, state, stage, message, remediation=remediation,
                         user_action=user_action, evidence=evidence, error=error)
            self._write(index)
            return task

    def _check_cancel(self, task_id: str, event: threading.Event) -> None:
        path = self.cancel_dir / f"{task_id}.cancel"
        if path.exists() or path.is_symlink():
            validate_private_file(path)
            event.set()
        if event.is_set():
            raise SetupError("SETUP_CANCELLED", "用户取消了运行环境准备",
                             "已有 Docker、已导入镜像与其他项目保留；可稍后重新准备")

    def _import_cancelled(self, task_id: str, event: threading.Event) -> bool:
        try:
            self._check_cancel(task_id, event)
        except (SetupError, OSError):
            # Fail closed while a loader is running; the worker records the
            # precise marker/state failure after the subprocess has ended.
            event.set()
            return True
        return False

    def _progress(self, task_id: str, event: threading.Event, done: int, total: int) -> None:
        self._check_cancel(task_id, event)
        with self._mutex:
            index = self._read()
            task = self._get_task(index, task_id)
            task.progress = {"downloaded_bytes": done, "total_bytes": total}
            task.updated_at = utcnow().isoformat()
            self._write(index)

    def _platform_supported(self) -> bool:
        if self.platform.get("os_name") != "Darwin" or self.platform.get("architecture") != "aarch64":
            return False
        try:
            validate_installer_lock(self.installer_lock)
            minimum = tuple(int(part) for part in str(self.installer_lock["minimum_macos"]).split("."))
            current = tuple(int(part) for part in str(self.platform.get("os_version", "")).split(".")[:2])
        except (ValueError, TypeError):
            return False
        return bool(current) and current >= minimum

    def _validate_host(self, host: dict[str, JSONValue]) -> None:
        if host.get("endpoint_local") is False:
            raise SetupError("DOCKER_ENDPOINT_UNSAFE", "Docker 当前目标不是已验证的本机 Unix 端点",
                             "切换到可信本机 Docker；不接受远程、TCP 或网页指定端点")
        if host.get("docker_error") == "permission_denied":
            raise SetupError("DOCKER_PERMISSION_DENIED", "Docker 权限检查失败", "在系统原生窗口检查权限；D1Env 不使用 sudo、chmod 或 Docker TCP")
        if host.get("docker_accessible") is True:
            if host.get("docker_os") not in {None, "linux"} or host.get("docker_architecture") not in {None, "aarch64"}:
                raise SetupError("DOCKER_PLATFORM_UNSUPPORTED", "已有 Docker 的系统或架构不匹配当前 ROS 工件",
                                 "当前候选只支持 Linux aarch64 Docker；保留原有安装，不自动替换")
            if host.get("compose_available") is False:
                raise SetupError("COMPOSE_UNAVAILABLE", "已有 Docker 缺少可用 Compose", "检查原有安装，D1Env 不替换已有 Docker 或下载插件")
        free = host.get("disk_free_bytes")
        if type(free) is int and free < 1024**3:
            raise SetupError("SETUP_DISK_SPACE", "运行环境准备可用磁盘不足 1 GiB", "释放用户自己的空间后重试，不自动删除镜像或其他项目")

    def _wait_ready(self, task_id: str, event: threading.Event) -> bool:
        deadline = time.monotonic() + self.wait_timeout_s
        self._update(task_id, "RUNNING", "wait_ready", "等待 Docker 与 Compose 的本机只读检查通过")
        while time.monotonic() < deadline:
            self._check_cancel(task_id, event)
            host = self.probe()
            self._validate_host(host)
            if self._docker_ready(host) is True:
                return True
            event.wait(self.wait_interval_s)
        self._update(task_id, "WAITING_USER", "native_setup", "Docker 尚未就绪，可能需要完成原生许可或系统设置",
                     remediation="在 Docker 原生窗口完成许可与设置后，返回点击重新检查；不收集系统密码",
                     user_action="check_again", evidence={"timeout_seconds": self.wait_timeout_s})
        return False

    def _worker(self, task_id: str, lease: _Lease, event: threading.Event) -> None:
        try:
            self._check_cancel(task_id, event)
            if not self._platform_supported():
                raise SetupError("SETUP_PLATFORM_UNSUPPORTED", "当前平台未支持本轮自动环境准备",
                                 "当前候选仅支持 Mac Apple Silicon；其他平台保留已有环境并使用 MOCK，不自动安装或导入")
            task = self._get_task(self._read(), task_id)
            resume_stage = task.stage
            host = self.probe()
            self._validate_host(host)
            self._update(task_id, "RUNNING", "detect", "已取得本机环境检测证据", evidence=host)
            if self._docker_ready(host) is not True:
                if not self._platform_supported():
                    raise SetupError("SETUP_PLATFORM_UNSUPPORTED", "当前系统尚未支持自动安装 Docker",
                                     "MOCK 可继续使用；Linux 与 Intel Mac 首次安装尚未验收")
                validate_installer_lock(self.installer_lock)
                if not self.native.app_exists():
                    if resume_stage == "native_setup":
                        self._update(task_id, "WAITING_USER", "native_setup", "系统安装窗口尚未完成，未找到 Docker.app",
                                     remediation="完成系统原生安装后返回重新检查；不会重复下载安装包", user_action="check_again")
                        return
                    if host.get("docker_error") != "missing" or host.get("docker_available") is not False:
                        self._update(task_id, "WAITING_USER", "native_setup", "已有或未知 Docker 环境未就绪，未尝试替换",
                                     remediation="检查原有 Docker 原生设置后返回重新检查", user_action="check_again")
                        return
                    if not task.license_accepted:
                        self._update(task_id, "WAITING_USER", "license", "需要你确认查看并接受 Docker 的许可及适用订阅条件",
                                     remediation="阅读官方许可；D1Env 不代替你接受 Docker 首次运行协议或订阅",
                                     user_action="accept_license", evidence={"license_url": self.installer_lock["license_url"], "auto_accept_license": False})
                        return
                    minimum = tuple(int(part) for part in str(self.installer_lock["minimum_macos"]).split("."))
                    try:
                        current = tuple(int(part) for part in str(self.platform.get("os_version", "")).split(".")[:2])
                    except ValueError:
                        current = ()
                    if not current or current < minimum:
                        raise SetupError("MACOS_VERSION_UNSUPPORTED", "macOS 版本缺失或低于安装包要求", "保留现有系统，检查发行包支持范围；不自动升级系统")
                    self._update(task_id, "RUNNING", "download", "下载锁定的官方 Docker 安装包", evidence={"url": self.installer_lock["url"], "sha256": self.installer_lock["sha256"]})
                    dmg = self.downloader.fetch(self.installer_lock, event,
                                                lambda done, total: self._progress(task_id, event, done, total))
                    self._check_cancel(task_id, event)
                    self._update(task_id, "RUNNING", "verify", "下载大小和 SHA-256 已校验；继续系统签名与 Gatekeeper 检查")
                    self._update(task_id, "RUNNING", "install", "准备官方 Docker 应用，保留任何已有安装")
                    evidence = self.native.install(dmg, self.installer_lock, task_id, event)
                    self._check_cancel(task_id, event)
                    if evidence.get("native_setup_required") is True:
                        self._update(task_id, "WAITING_USER", "native_setup", "请在 macOS 原生窗口完成应用安装及必要授权",
                                     remediation="完成后返回点击重新检查；D1Env 不收集密码、不使用 sudo", user_action="check_again", evidence=evidence)
                        return
                    self._update(task_id, "RUNNING", "install", "应用准备步骤已完成，正在重新核对已有应用", evidence=evidence)
                self._check_cancel(task_id, event)
                self._update(task_id, "RUNNING", "start", "打开经过签名与 Gatekeeper 核验的 Docker Desktop")
                evidence = self.native.start(self.installer_lock, event)
                self._update(task_id, "RUNNING", "start", "已打开 Docker 原生窗口，许可与系统设置由你完成", evidence=evidence)
                if not self._wait_ready(task_id, event):
                    return
            self._check_cancel(task_id, event)
            self._update(task_id, "RUNNING", "import_image", "准备随 D1Env 锁定的 ROS 软件镜像（不启动机器人业务）")
            image = self.prepare_image(lambda: self._import_cancelled(task_id, event))
            self._check_cancel(task_id, event)
            if image.get("artifact_ready") is not True:
                raise SetupError("IMAGE_PREPARATION_UNVERIFIED", "软件镜像准备未取得严格通过证据",
                                 "检查完整发行包及镜像包，不能把下载或容器运行当作功能就绪")
            ready, current_host, current_image = self._current()
            if ready is not True:
                raise SetupError("RUNTIME_READINESS_UNVERIFIED", "最终只读检查未确认当前软件运行环境",
                                 "检查 Docker 与固定镜像后重新准备；未知状态不会显示正常",
                                 {"host": current_host, "artifact": current_image})
            self._update(task_id, "SUCCEEDED", "complete", "当前运行环境已准备，可继续预览和部署 ROS 软件测试",
                         remediation="这只证明运行环境和镜像；ROS 通信需部署后检查，D1 真机仍未支持",
                         evidence={"host": current_host, "artifact": current_image, "image_preparation": image})
        except Exception as exc:  # noqa: BLE001 - persist any worker failure without running recovery actions.
            error = exc if isinstance(exc, SetupError) else SetupError(
                "RUNTIME_PREPARATION_FAILED", "运行环境准备步骤失败",
                "保留本任务证据，检查失败环节后显式重试；已有 Docker 与其他项目保留",
                {"exception_type": type(exc).__name__},
            )
            try:
                self._check_cancel(task_id, event)
            except SetupError as cancel_error:
                error = cancel_error
            try:
                task = self._get_task(self._read(), task_id)
                self._update(task_id, "CANCELLED" if error.code == "SETUP_CANCELLED" else "FAILED",
                             task.stage, error.message, remediation=error.remediation,
                             evidence=error.evidence, error={"code": error.code, "message": error.message,
                                                            "remediation": error.remediation, "evidence": error.evidence})
            except (ValueError, OSError):
                pass  # Unsafe state is never repaired by weakening permissions.
        finally:
            with self._mutex:
                try:
                    task = self._get_task(self._read(), task_id)
                    if task.state == "WAITING_USER":
                        self._check_cancel(task_id, event)
                except SetupError as exc:
                    if exc.code == "SETUP_CANCELLED":
                        self._update(task_id, "CANCELLED", task.stage, "已取消环境准备，保留已有 Docker 与镜像")
                finally:
                    self._cancel_events.pop(task_id, None)
                    lease.close()
