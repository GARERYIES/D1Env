from typing import Protocol

from d1env.models import ExecutionContext, Operation, OperationResult


class Executor(Protocol):
    def execute(self, operation: Operation, context: ExecutionContext) -> OperationResult:
        """Execute a whitelisted operation and return observed MOCK evidence."""
        ...
