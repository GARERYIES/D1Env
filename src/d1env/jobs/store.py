"""SQLite state; every write uses a short transaction and its own connection."""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from d1env.models import DeploymentPlan, JobEvent, JobSnapshot, JobState, JSONValue, utcnow

TERMINAL_STATES = ("SUCCEEDED", "BLOCKED", "FAILED", "CANCELLED", "INTERRUPTED")


class JobConflict(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL,
                    target_id TEXT NOT NULL, state TEXT NOT NULL,
                    payload TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_target ON jobs(target_id)
                    WHERE state NOT IN ('SUCCEEDED','BLOCKED','FAILED','CANCELLED','INTERRUPTED');
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT PRIMARY KEY, plan_id TEXT NOT NULL, job_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    job_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(job_id, seq)
                );
                CREATE TABLE IF NOT EXISTS resources (
                    job_id TEXT NOT NULL, resource_id TEXT NOT NULL,
                    device INTEGER NOT NULL, inode INTEGER NOT NULL,
                    cleaned INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(job_id, resource_id)
                );
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _plan_payload(plan: DeploymentPlan) -> str:
        return json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def _save_plan(self, connection: sqlite3.Connection, plan: DeploymentPlan) -> None:
        payload = self._plan_payload(plan)
        row = connection.execute(
            "SELECT payload FROM plans WHERE plan_id=?", (plan.plan_id,)
        ).fetchone()
        if row and row["payload"] != payload:
            raise JobConflict(
                "PLAN_ID_CONFLICT", "计划保存失败：同一计划 ID 的内容已改变；请重新预览计划。"
            )
        connection.execute("INSERT OR IGNORE INTO plans VALUES (?,?)", (plan.plan_id, payload))

    def save_plan(self, plan: DeploymentPlan) -> None:
        with self._transaction() as connection:
            self._save_plan(connection, plan)

    def get_plan(self, plan_id: str) -> DeploymentPlan:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM plans WHERE plan_id=?", (plan_id,)
            ).fetchone()
        if row is None:
            raise KeyError(plan_id)
        return DeploymentPlan.model_validate_json(row["payload"])

    @staticmethod
    def _get_job(connection: sqlite3.Connection, job_id: str) -> JobSnapshot:
        row = connection.execute("SELECT payload FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return JobSnapshot.model_validate_json(row["payload"])

    def get_job(self, job_id: str) -> JobSnapshot:
        with self._connection() as connection:
            return self._get_job(connection, job_id)

    def list_jobs(self) -> list[JobSnapshot]:
        with self._connection() as connection:
            rows = connection.execute("SELECT payload FROM jobs ORDER BY rowid DESC").fetchall()
        return [JobSnapshot.model_validate_json(row["payload"]) for row in rows]

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        job: JobSnapshot,
        event_type: str,
        message: str,
        evidence: dict[str, JSONValue],
        operation_id: str | None = None,
    ) -> JobEvent:
        row = connection.execute(
            "SELECT COALESCE(MAX(seq),0)+1 AS seq FROM events WHERE job_id=?",
            (job.job_id,),
        ).fetchone()
        event = JobEvent(
            job_id=job.job_id,
            seq=row["seq"],
            timestamp=utcnow(),
            event_type=event_type,
            operation_id=operation_id,
            mode=job.mode,
            origin="mock",
            message=message,
            evidence=evidence,
        )
        connection.execute(
            "INSERT INTO events VALUES (?,?,?)", (job.job_id, event.seq, event.model_dump_json())
        )
        return event

    def append_event(
        self,
        job_id: str,
        event_type: str,
        message: str,
        evidence: dict[str, JSONValue] | None = None,
        operation_id: str | None = None,
    ) -> JobEvent:
        with self._transaction() as connection:
            return self._append_event(
                connection,
                self._get_job(connection, job_id),
                event_type,
                message,
                evidence or {},
                operation_id,
            )

    def get_events(self, job_id: str) -> list[JobEvent]:
        with self._connection() as connection:
            self._get_job(connection, job_id)
            rows = connection.execute(
                "SELECT payload FROM events WHERE job_id=? ORDER BY seq",
                (job_id,),
            ).fetchall()
        return [JobEvent.model_validate_json(row["payload"]) for row in rows]

    def claim(
        self,
        plan: DeploymentPlan,
        key: str,
        acquire_lock: Callable[[], None],
    ) -> tuple[JobSnapshot, bool]:
        """Bind request and acquire the target lock transactionally before creating a worker."""
        with self._transaction() as connection:
            binding = connection.execute(
                "SELECT plan_id,job_id FROM idempotency_keys WHERE key=?",
                (key,),
            ).fetchone()
            if binding:
                if binding["plan_id"] != plan.plan_id:
                    raise JobConflict(
                        "IDEMPOTENCY_CONFLICT", "重复请求失败：该请求键已绑定另一计划；请重新预览。"
                    )
                self._save_plan(connection, plan)
                return self._get_job(connection, binding["job_id"]), False
            self._save_plan(connection, plan)
            active = connection.execute(
                "SELECT job_id,plan_id FROM jobs WHERE target_id=? "
                "AND state NOT IN ('SUCCEEDED','BLOCKED','FAILED','CANCELLED','INTERRUPTED')",
                (plan.target_id,),
            ).fetchone()
            if active:
                if active["plan_id"] != plan.plan_id:
                    raise JobConflict(
                        "TARGET_BUSY", "部署失败：该电脑已有另一活动计划；等待完成或取消后重试。"
                    )
                job = self._get_job(connection, active["job_id"])
            else:
                succeeded = connection.execute(
                    "SELECT job_id FROM jobs WHERE target_id=? AND plan_id=? AND state='SUCCEEDED' "
                    "ORDER BY rowid DESC LIMIT 1",
                    (plan.target_id, plan.plan_id),
                ).fetchone()
                if succeeded:
                    job = self._get_job(connection, succeeded["job_id"])
                else:
                    acquire_lock()
                    now = utcnow()
                    job = JobSnapshot(
                        job_id=uuid4().hex,
                        plan_id=plan.plan_id,
                        target_id=plan.target_id,
                        mode="mock",
                        state="PLANNED",
                        verified_scope="mock",
                        created_at=now,
                        updated_at=now,
                    )
                    connection.execute(
                        "INSERT INTO jobs(job_id,plan_id,target_id,state,payload) VALUES (?,?,?,?,?)",
                        (job.job_id, job.plan_id, job.target_id, job.state, job.model_dump_json()),
                    )
                    self._append_event(
                        connection,
                        job,
                        "state",
                        "MOCK 作业已创建，尚未部署真机。",
                        {"state": "PLANNED"},
                    )
                    connection.execute(
                        "INSERT INTO idempotency_keys VALUES (?,?,?)",
                        (key, plan.plan_id, job.job_id),
                    )
                    return job, True
            connection.execute(
                "INSERT INTO idempotency_keys VALUES (?,?,?)", (key, plan.plan_id, job.job_id)
            )
            return job, False

    def transition(
        self,
        job_id: str,
        state: JobState,
        message: str,
        *,
        operation_id: str | None = None,
        error_code: str | None = None,
        evidence: dict[str, JSONValue] | None = None,
        release_lock: Callable[[], None] | None = None,
    ) -> JobSnapshot:
        with self._transaction() as connection:
            job = self._get_job(connection, job_id)
            if job.state in TERMINAL_STATES:
                return job
            requested = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if state == "SUCCEEDED" and requested["cancel_requested"]:
                return job
            changed = job.model_copy(
                update={
                    "state": state,
                    "current_operation_id": operation_id,
                    "updated_at": utcnow(),
                    "error_code": error_code,
                }
            )
            connection.execute(
                "UPDATE jobs SET state=?,payload=? WHERE job_id=?",
                (state, changed.model_dump_json(), job_id),
            )
            details: dict[str, JSONValue] = {"state": state, **(evidence or {})}
            self._append_event(connection, changed, "state", message, details, operation_id)
            # Unlock before commit while the write transaction still prevents another claim.
            if state in TERMINAL_STATES and release_lock:
                release_lock()
            return changed

    def request_cancel(self, job_id: str) -> JobSnapshot:
        with self._transaction() as connection:
            job = self._get_job(connection, job_id)
            if job.state not in TERMINAL_STATES:
                previous = connection.execute(
                    "SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)
                ).fetchone()
                connection.execute("UPDATE jobs SET cancel_requested=1 WHERE job_id=?", (job_id,))
                if not previous["cancel_requested"]:
                    self._append_event(
                        connection,
                        job,
                        "cancel_requested",
                        "已请求取消 MOCK 作业；等待当前步骤停止并清理本作业资源。",
                        {},
                    )
            return job

    def is_cancelled(self, job_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return bool(row["cancel_requested"])

    def register_resource(self, job_id: str, resource_id: str, device: int, inode: int) -> None:
        with self._transaction() as connection:
            self._get_job(connection, job_id)
            connection.execute(
                "INSERT OR IGNORE INTO resources VALUES (?,?,?,?,0)",
                (job_id, resource_id, device, inode),
            )

    def resources(self, job_id: str) -> list[dict[str, JSONValue]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT resource_id,device,inode,cleaned FROM resources WHERE job_id=?", (job_id,)
            ).fetchall()
        return [
            {
                "resource_id": row["resource_id"],
                "device": row["device"],
                "inode": row["inode"],
                "cleaned": bool(row["cleaned"]),
            }
            for row in rows
        ]

    def resource_cleaned(self, job_id: str, resource_id: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE resources SET cleaned=1 WHERE job_id=? AND resource_id=?",
                (job_id, resource_id),
            )
