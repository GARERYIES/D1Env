from typing import Protocol

from d1env.models import ArtifactRef, ExecutionContext, JSONValue, Operation, OperationResult


class Executor(Protocol):
    def execute(self, operation: Operation, context: ExecutionContext) -> OperationResult:
        """Execute a whitelisted operation and return evidence in its declared scope."""
        ...


class ManagedExecutor(Executor, Protocol):
    def cleanup(self, context: ExecutionContext) -> list[str]: ...

    def inventory(self, context: ExecutionContext) -> dict[str, JSONValue]: ...

    def verify_running(self, context: ExecutionContext, artifact: ArtifactRef) -> OperationResult: ...
