from pathlib import Path

from .catalog import load_catalog
from .doctor import diagnose, inspect_host
from .jobs.engine import JobEngine
from .jobs.store import Store
from .models import DeploymentRequest, JobSnapshot, PlanResolution, Telemetry
from .planner import resolve
from .process import ProbeRunner
from .reports import build_report, markdown_report


class ApplicationService:
    def __init__(self, root_dir: Path, state_dir: Path, runner: ProbeRunner | None = None) -> None:
        self.root_dir = root_dir
        self.catalog = load_catalog(root_dir / "profiles")
        self.runner = runner or ProbeRunner()
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = Store(state_dir / "jobs.sqlite")
        self.engine = JobEngine(self.store, work_dir=state_dir / "resources")

    def doctor(self, request: DeploymentRequest) -> dict[str, object]:
        facts = inspect_host(request.target_id, self.runner)
        return {"facts": facts.model_dump(mode="json"),
                "checks": [check.model_dump(mode="json") for check in diagnose(request, facts)],
                "telemetry": Telemetry().model_dump(mode="json")}

    def preview(self, request: DeploymentRequest) -> PlanResolution:
        resolution = resolve(request, inspect_host(request.target_id, self.runner), self.catalog)
        if resolution.plan is not None:
            self.store.save_plan(resolution.plan)
        return resolution

    def start(self, plan_id: str, idempotency_key: str) -> JobSnapshot:
        saved = self.store.get_plan(plan_id)
        current = self.preview(saved.request)
        if current.plan is None:
            raise ValueError("PREFLIGHT_BLOCKED: 必要条件变化，请重新检查和预览")
        if current.plan.plan_id != saved.plan_id:
            raise ValueError("PLAN_CHANGED: 配置或执行主机变化，请重新确认计划")
        return self.engine.submit(saved, idempotency_key)

    def report(self, job_id: str, mask_identifiers: bool = True) -> dict[str, object]:
        job = self.engine.get(job_id)
        plan = self.store.get_plan(job.plan_id)
        facts = inspect_host("local", self.runner)
        report = build_report(job, diagnose(plan.request, facts), self.engine.get_events(job_id),
                              mask_identifiers=mask_identifiers)
        return {"report": report.model_dump(mode="json"), "markdown": markdown_report(report)}
