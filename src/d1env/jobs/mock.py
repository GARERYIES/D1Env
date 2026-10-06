"""Deterministic fault-labelled simulation; no network, process, Docker or SDK calls."""

import os
import time

from d1env.models import ExecutionContext, JSONValue, Operation, OperationResult

MOCK_OPERATION_IDS = frozenset(
    {"preflight", "acquire", "configure", "start", "verify", "verify_failure"}
)


class MockExecutor:
    def __init__(self, delay_s: float = 0.3):
        if not 0 <= delay_s <= 0.6:
            raise ValueError("MOCK delay must be between 0 and 0.6 seconds")
        self.delay_s = delay_s

    def execute(self, operation: Operation, context: ExecutionContext) -> OperationResult:
        if (
            context.mode != "mock"
            or operation.kind != "mock_step"
            or operation.operation_id not in MOCK_OPERATION_IDS
        ):
            raise ValueError("only whitelisted MOCK operations are available")
        started = time.monotonic()
        deadline = started + operation.timeout_s
        delay_until = started + self.delay_s
        while time.monotonic() < delay_until:
            if context.is_cancelled():
                return OperationResult(
                    operation_id=operation.operation_id,
                    status="cancelled",
                    message="MOCK 当前步骤已响应取消。",
                )
            now = time.monotonic()
            if now >= deadline:
                return OperationResult(
                    operation_id=operation.operation_id,
                    status="failed",
                    error_code="OPERATION_TIMEOUT",
                    message="MOCK 步骤超时；检测证据：软件计时超过步骤期限；请检查步骤设置后重试。",
                    evidence={"timeout_s": operation.timeout_s},
                )
            time.sleep(max(0.0, min(0.02, delay_until - now, deadline - now)))
        if context.is_cancelled():
            return OperationResult(
                operation_id=operation.operation_id,
                status="cancelled",
                message="MOCK 当前步骤已响应取消。",
            )
        if time.monotonic() >= deadline:
            return OperationResult(
                operation_id=operation.operation_id,
                status="failed",
                error_code="OPERATION_TIMEOUT",
                message="MOCK 步骤超时；请检查步骤期限后重试。",
            )
        if operation.operation_id == "verify_failure":
            return OperationResult(
                operation_id=operation.operation_id,
                status="failed",
                error_code="MOCK_READINESS_FAILED",
                message="MOCK 故障注入：就绪检查失败；证据：<script>window.__d1env_injected=true</script>；请使用新的请求键重试演示。",
                evidence={"fault_injection": True, "mock_ready": False},
            )
        resource_ids: list[str] = []
        if operation.operation_id == "acquire":
            directory = context.work_dir
            if directory.is_symlink() or directory.resolve() != directory.absolute():
                raise ValueError("MOCK resource directory cannot be a symbolic link")
            resource_id = "acquired.mock"
            descriptor = os.open(
                directory / resource_id, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "w") as resource:
                resource.write("MOCK resource; owned only by this job\n")
            resource_ids.append(resource_id)
        evidence: dict[str, JSONValue] = {"mock_step_completed": True}
        if operation.operation_id == "start":
            evidence["process_alive"] = True
        if operation.operation_id == "verify":
            evidence["mock_ready"] = True
        return OperationResult(
            operation_id=operation.operation_id,
            status="succeeded",
            message=f"MOCK {operation.label} 完成；仅验证演示步骤。",
            evidence=evidence,
            resource_ids=resource_ids,
        )
