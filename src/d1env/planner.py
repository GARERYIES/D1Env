import hashlib
import json

from . import __version__
from .models import (
    Blocker,
    Catalog,
    DeploymentPlan,
    DeploymentRequest,
    HostFacts,
    Operation,
    PlanResolution,
)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def resolve(request: DeploymentRequest, facts: HostFacts, catalog: Catalog) -> PlanResolution:
    profile = next((p for p in catalog.profiles if p.profile_id == request.profile_id), None)
    blockers: list[Blocker] = []

    def block(code: str, message: str, field: str) -> None:
        blockers.append(Blocker(code=code, message=message,
                                remediation="选择 MOCK 演示；真实适配需后续来源、工件及集成证据", field=field))

    if profile is None or profile.profile_id == "unknown":
        block("PROFILE_UNVERIFIED", "型号未确认，禁止映射到任何真实 SDK", "profile_id")
    elif request.mode == "mock" and profile.kind != "mock":
        block("MODE_PROFILE_MISMATCH", "真实型号不能隐式转换为 MOCK", "mode")
    elif request.mode == "real_readonly":
        block("ADAPTER_UNAVAILABLE", "本轮只有 MOCK 执行器，真实只读适配尚未实现", "mode")
        if not profile.artifact_requirements:
            block("ARTIFACT_UNAVAILABLE", "缺少已校验的真实工件与不可变标识", "artifact_requirements")
        if profile.firmware_rules is None:
            block("FIRMWARE_UNVERIFIED", "固件兼容范围尚未验证", "firmware_rules")
    if facts.disk_free_bytes is None or facts.disk_free_bytes < 104857600:
        block("DISK_UNVERIFIED", "项目磁盘未取得或低于演示软件阈值", "disk_free_bytes")
    if blockers or profile is None:
        return PlanResolution(blockers=blockers)
    operations = tuple(Operation(operation_id=opid, label=label,
                                 required_evidence=("mock_ready",) if opid.startswith("verify") else ())
                       for opid, label in [
                           ("preflight", "复核 MOCK 条件"), ("acquire", "模拟准备工件（没有真实下载）"),
                           ("configure", "建立本作业 MOCK 资源"), ("start", "模拟服务启动"),
                           ("verify_failure" if request.demo_scenario == "verify_failure" else "verify",
                            "故障注入：模拟就绪检查失败" if request.demo_scenario == "verify_failure" else "验证 MOCK 软件流程"),
                       ])
    config_digest = canonical_hash({"profile": profile.model_dump(mode="json"),
                                    "request": request.model_dump(mode="json"),
                                    "app_version": __version__,
                                    "host": {"os": facts.os_name, "version": facts.os_version, "architecture": facts.architecture}})
    prototype = DeploymentPlan(plan_id="", mode=request.mode, target_id=request.target_id,
                               profile_id=profile.profile_id, operations=operations,
                               required_evidence=("mock_ready",), verified_scope="mock",
                               profile_revision=profile.profile_revision, config_digest=config_digest,
                               request=request)
    return PlanResolution(plan=prototype.model_copy(update={"plan_id": canonical_hash(prototype.model_dump(mode="json"))}))
