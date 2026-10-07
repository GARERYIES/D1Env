import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field, ValidationError

from .catalog import load_catalog
from .doctor import diagnose, inspect_host
from .jobs.engine import JobEngine
from .jobs.store import Store
from .models import (
    DeploymentRequest,
    JobSnapshot,
    JSONValue,
    PlanResolution,
    StrictModel,
    Telemetry,
)
from .planner import resolve
from .process import ProbeRunner
from .reports import build_report, markdown_report
from .runtime import ensure_private_state_dir

if TYPE_CHECKING:
    from .setup.manager import SetupManager


class TrustedROSBundle(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    filename: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0, le=8 * 1024**3)
    source: str
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    architecture: str


class ApplicationService:
    def __init__(self, root_dir: Path, state_dir: Path, runner: ProbeRunner | None = None) -> None:
        self.root_dir = root_dir
        self.catalog = load_catalog(root_dir / "profiles")
        self.runner = runner or ProbeRunner()
        state_dir = ensure_private_state_dir(state_dir.absolute())
        self.store = Store(state_dir / "jobs.sqlite")
        self.engine = JobEngine(self.store, work_dir=state_dir / "resources")
        self._runtime_setup: SetupManager | None = None

    @property
    def runtime_setup(self) -> "SetupManager":
        from .setup.manager import SetupManager
        if self._runtime_setup is None:
            record = self.root_dir / "docs/build/DOCKER_DESKTOP_LOCK.json"
            lock: dict[str, JSONValue] = {}
            if record.is_file() and not record.is_symlink() and record.stat().st_size <= 1024**2:
                try:
                    parsed = json.loads(record.read_bytes())
                    if isinstance(parsed, dict):
                        lock = parsed
                except (OSError, ValueError):
                    pass
            self._runtime_setup = SetupManager(self.store.path.parent, installer_lock=lock,
                probe=self._runtime_probe, prepare_image=self._prepare_runtime_image,
                image_probe=self._runtime_image_probe)
        return self._runtime_setup

    def _runtime_probe(self) -> dict[str, JSONValue]:
        from .docker.endpoint import resolve_endpoint
        facts: dict[str, JSONValue] = inspect_host("local", self.runner).model_dump(mode="json")
        try:
            facts["endpoint_local"] = resolve_endpoint().local
        except ValueError as exc:
            facts["endpoint_local"] = None
            facts["endpoint_error"] = str(exc)
        return facts

    def _runtime_image_probe(self) -> dict[str, JSONValue]:
        from .docker.client import DockerClient
        metadata = self.ros_image_metadata()["trusted_bundle"]
        if not isinstance(metadata, dict):
            return {"artifact_ready": False, "reason": "trusted ROS metadata unavailable"}
        result = DockerClient().run(("image", "inspect", str(metadata["image_id"])))
        if result.timed_out or result.cancelled:
            return {"artifact_ready": None, "reason": "image observation unavailable"}
        if result.returncode != 0:
            return {"artifact_ready": False, "reason": "locked image unavailable", "exit_code": result.returncode}
        try:
            records = json.loads(result.stdout)
            item = records[0] if isinstance(records, list) and len(records) == 1 else {}
            raw_architecture = item.get("Architecture")
            architecture = {"arm64": "aarch64", "amd64": "x86_64"}.get(str(raw_architecture), raw_architecture)
            source = item.get("Config", {}).get("Labels", {}).get("io.d1env.source")
            ready = (item.get("Id") == metadata["image_id"] and architecture == metadata["architecture"]
                     and source == metadata["source"])
            return {"artifact_ready": ready, "image_id": item.get("Id"),
                    "architecture": architecture, "source": source, "origin": "docker"}
        except (ValueError, TypeError, AttributeError, KeyError):
            return {"artifact_ready": None, "reason": "invalid Docker image observation"}

    def _prepare_runtime_image(self, is_cancelled: Callable[[], bool] = lambda: False) -> dict[str, JSONValue]:
        from .setup.models import SetupError
        observed = self._runtime_image_probe()
        if observed.get("artifact_ready") is True:
            return {**observed, "status": "reused"}
        if observed.get("artifact_ready") is None:
            raise SetupError("RUNTIME_IMAGE_UNKNOWN", "配套镜像身份尚未取得", "检查 Docker 后重新准备；不会把未知镜像当作可用", observed)
        metadata = self.ros_image_metadata()["trusted_bundle"]
        if not isinstance(metadata, dict):
            raise SetupError("RUNTIME_IMAGE_BLOCKED", "随包 ROS 来源锁缺失", "请使用完整发行包")
        filename = str(metadata["filename"])
        candidates = [self.root_dir / "bundles" / filename]
        if (self.root_dir / ".git").is_dir():
            candidates.append(self.root_dir / "outputs/D1Env-M3" / filename)
        bundle = next((path for path in candidates if path.is_file() and not path.is_symlink()), None)
        if bundle is None:
            raise SetupError("RUNTIME_IMAGE_BUNDLE_MISSING", "程序没有取得配套 ROS 镜像包", "请使用含镜像的完整发行包；旧包仍可在页面手动导入")
        receipt = self.import_ros_image(bundle, is_cancelled=is_cancelled)
        current = self._runtime_image_probe()
        if current.get("artifact_ready") is not True:
            raise SetupError("RUNTIME_IMAGE_NOT_VERIFIED", "导入后镜像身份没有通过复核", "保留现有镜像，检查导入证据后重试", current)
        return {**current, "status": receipt.get("status"), "bundle_sha256": metadata["sha256"]}

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
        source_file = self.root_dir / "docs/research/UPSTREAM_LOCK.json"
        sources = json.loads(source_file.read_text()) if source_file.is_file() else {
            "retrieval_status": "blocked", "reason": "installed source lock unavailable"}
        for name, filename in (("ros_probe_build", "ROS_PROBE_LOCK.json"),
                               ("ros_probe_offline", "ROS_PROBE_OFFLINE.json")):
            lock_file = self.root_dir / "docs/build" / filename
            sources[name] = json.loads(lock_file.read_text()) if lock_file.is_file() else {
                "retrieval_status": "blocked", "reason": f"installed {filename} unavailable"}
        report = build_report(job, diagnose(plan.request, facts), self.engine.get_events(job_id),
                              mask_identifiers=mask_identifiers,
                              source_locks=sources)
        return {"report": report.model_dump(mode="json"), "markdown": markdown_report(report)}

    def stop(self, job_id: str) -> JobSnapshot:
        return self.engine.stop(job_id)

    def ros_image_metadata(self) -> dict[str, JSONValue]:
        """Only the installed release can select the image and expected bundle hash."""
        blocked: dict[str, JSONValue] = {"trusted_bundle": None,
            "blocked_reason": "随包离线镜像元数据不可用或不匹配；请使用完整且适合此架构的发行包。"}
        lock = self.root_dir / "docs/build/ROS_PROBE_OFFLINE.json"
        try:
            if lock.is_symlink() or not lock.is_file() or lock.stat().st_size > 1024**2:
                return blocked
            record = json.loads(lock.read_text())
            bundle = TrustedROSBundle.model_validate({key: record[key]
                for key in TrustedROSBundle.model_fields})
            profile = next(item for item in self.catalog.profiles if item.profile_id == "ros-probe")
            if len(profile.artifact_requirements) != 1:
                return blocked
            artifact = profile.artifact_requirements[0]
            if (artifact.kind != "local_build" or artifact.source != "d1env/ros-probe"
                    or bundle.source != artifact.source or bundle.image_id != artifact.immutable_id
                    or bundle.architecture != artifact.architecture):
                return blocked
            return {"trusted_bundle": bundle.model_dump(mode="json"), "blocked_reason": None}
        except (OSError, ValueError, KeyError, TypeError, StopIteration, ValidationError):
            return blocked

    def import_ros_image(self, path: Path, is_cancelled: Callable[[], bool] = lambda: False) -> dict[str, JSONValue]:
        from .docker.offline import ROSImageImporter
        metadata = self.ros_image_metadata()["trusted_bundle"]
        if not isinstance(metadata, dict):
            raise ValueError("OFFLINE_IMPORT_BLOCKED: 缺少匹配的发行元数据；不能导入任意镜像。")  # noqa: TRY004 - missing release data is a blocked operation
        artifact = next(item for item in self.catalog.profiles if item.profile_id == "ros-probe").artifact_requirements[0]
        importer = ROSImageImporter(expected_artifact=artifact,
            trusted_bundle_sha256=str(metadata["sha256"]), state_dir=self.store.path.parent)
        return importer.import_bundle(path, is_cancelled=is_cancelled)
