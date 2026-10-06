import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

Mode = Literal["mock", "real_readonly"]
CheckStatus = Literal["PASS", "WARN", "FAIL", "UNKNOWN", "SKIPPED"]
EvidenceOrigin = Literal["mock", "local_probe", "docker", "sdk", "operator"]
JobState = Literal[
    "PLANNED", "PREFLIGHT", "ACQUIRING", "CONFIGURING", "STARTING", "VERIFYING",
    "SUCCEEDED", "BLOCKED", "FAILED", "CANCELLED", "INTERRUPTED",
]
CapabilityStatus = Literal[
    "not_implemented", "documented", "implemented", "integration_verified", "hardware_verified",
]
JSONValue = JsonValue


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True)


class Capability(StrictModel):
    declared_by_vendor: bool = False
    status: CapabilityStatus = "not_implemented"
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str


class RuntimeRequirements(StrictModel):
    os_name: str | None = None
    os_version: str | None = None
    gpu_required: bool = False
    min_disk_bytes: int = Field(default=104857600, ge=0)


class ArtifactRef(StrictModel):
    kind: Literal["mock", "registry", "local_build"]
    source: str | None = None
    architecture: str | None = None
    immutable_id: str | None = None

    @model_validator(mode="after")
    def immutable_real_artifacts(self) -> "ArtifactRef":
        if self.kind != "mock" and not all([self.source, self.architecture, self.immutable_id]):
            raise ValueError("real artifact requires source, architecture and immutable identifier")
        if self.kind != "mock" and (
            self.immutable_id is None or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.immutable_id)
            or self.immutable_id == "sha256:" + "0" * 64
        ):
            raise ValueError("real artifact requires a non-placeholder SHA-256 identifier")
        return self


class Profile(StrictModel):
    schema_version: Literal[1] = 1
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str
    kind: Literal["mock", "hardware"]
    profile_revision: str
    vendor: str | None
    sdk_family: Literal["edu_ultra_zsl_1", "edu_ultra_zsl_1w", "maxpro_legacy"] | None
    variant: str | None
    architectures: list[Literal["x86_64", "aarch64"]]
    runtime_requirements: RuntimeRequirements
    firmware_rules: list[str] | None = None
    capabilities: dict[str, Capability]
    sensor_contract: list[str] = Field(default_factory=list)
    network_requirements: list[Literal["none", "documented_unverified"]]
    artifact_requirements: list[ArtifactRef] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    unverified_reason: str | None = None

    @model_validator(mode="after")
    def separation(self) -> "Profile":
        if self.kind == "mock" and self.sdk_family is not None:
            raise ValueError("mock profile cannot select vendor SDK")
        return self


class Catalog(StrictModel):
    schema_version: Literal[1] = 1
    profiles: list[Profile]

    @model_validator(mode="after")
    def unique(self) -> "Catalog":
        ids = [p.profile_id for p in self.profiles]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate profile_id")
        return self


class DeploymentRequest(StrictModel):
    mode: Mode = "mock"
    profile_id: str = Field(default="demo", pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    target_id: Literal["local"] = "local"
    task: Literal["demo", "diagnostics"] = "demo"
    demo_scenario: Literal["success", "verify_failure"] = "success"


class HostFacts(StrictModel):
    target_id: Literal["local"] = "local"
    os_name: str | None
    os_version: str | None
    architecture: str | None
    docker_available: bool | None
    docker_accessible: bool | None
    compose_available: bool | None
    disk_free_bytes: int | None
    gpu_available: bool | None
    checked_at: datetime
    docker_error: Literal["missing", "daemon_stopped", "permission_denied", "timeout", "unknown"] | None = None
    interfaces: list[str] = Field(default_factory=list)

    @field_validator("checked_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timezone required")
        return value.astimezone(timezone.utc)


class CheckResult(StrictModel):
    code: str
    status: CheckStatus
    reason: str
    remediation: str
    origin: EvidenceOrigin
    observed_at: datetime
    evidence: dict[str, JsonValue] = Field(default_factory=dict)


class Blocker(StrictModel):
    code: str
    message: str
    remediation: str
    field: str | None = None


class Operation(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: str
    kind: Literal["mock_step"] = "mock_step"
    label: str
    timeout_s: float = Field(default=5.0, gt=0, le=60)
    reversible: bool = True
    required_evidence: tuple[str, ...] = ()


class DeploymentPlan(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_id: str
    mode: Mode
    target_id: Literal["local"]
    profile_id: str
    operations: tuple[Operation, ...]
    required_evidence: tuple[str, ...]
    verified_scope: Literal["mock"]
    profile_revision: str
    config_digest: str
    request: DeploymentRequest = Field(default_factory=DeploymentRequest)
    download_bytes: int | None = None
    directories: tuple[str, ...] = ("项目内的 MOCK 作业目录",)
    services: tuple[str, ...] = ("MOCK 演示 worker",)
    permissions: tuple[str, ...] = ("仅写项目任务数据库与 MOCK 资源",)
    network: Literal["none"] = "none"


class PlanResolution(StrictModel):
    plan: DeploymentPlan | None = None
    blockers: list[Blocker] = Field(default_factory=list)


class OperationResult(StrictModel):
    operation_id: str
    status: Literal["succeeded", "failed", "cancelled"]
    origin: Literal["mock"] = "mock"
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    error_code: str | None = None
    message: str
    resource_ids: list[str] = Field(default_factory=list)


class JobSnapshot(StrictModel):
    job_id: str
    plan_id: str
    target_id: Literal["local"]
    mode: Mode
    state: JobState
    verified_scope: Literal["mock"]
    current_operation_id: str | None = None
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


class JobEvent(StrictModel):
    job_id: str
    seq: int = Field(ge=1)
    timestamp: datetime
    event_type: str
    operation_id: str | None = None
    mode: Mode
    origin: Literal["mock"]
    message: str
    evidence: dict[str, JsonValue] = Field(default_factory=dict)


class ExecutionContext(StrictModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    job_id: str
    target_id: Literal["local"]
    mode: Mode
    work_dir: Path
    is_cancelled: Callable[[], bool]
    emit: Callable[[JobEvent], None]


class ProbeResult(StrictModel):
    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    observed_at: datetime


class Telemetry(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True, allow_inf_nan=False)
    status: CheckStatus = "UNKNOWN"
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    pose: list[float] | None = None
    observed_at: datetime | None = None
    origin: EvidenceOrigin | None = None

    @model_validator(mode="after")
    def no_unverified_health(self) -> "Telemetry":
        if self.status == "PASS":
            if self.battery_percent is None or not self.pose:
                raise ValueError("missing telemetry samples cannot be PASS")
            if self.observed_at is None or self.observed_at.tzinfo is None or self.origin is None:
                raise ValueError("PASS telemetry requires timestamp and evidence origin")
            age = (utcnow() - self.observed_at).total_seconds()
            if age < 0 or age > 5:
                raise ValueError("stale telemetry cannot be PASS (5s software test threshold)")
        return self


class DiagnosticReport(StrictModel):
    schema_version: Literal[1] = 1
    mode: Mode
    verified_scope: Literal["mock"]
    job: dict[str, JsonValue]
    checks: list[dict[str, JsonValue]]
    events: list[dict[str, JsonValue]]
    source_locks: dict[str, JsonValue]
    unverified_items: list[str]
    redactions: list[str]
