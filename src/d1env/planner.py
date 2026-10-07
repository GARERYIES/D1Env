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
                                remediation="检查本地 Docker/Compose 与随包工件，确认架构和磁盘条件后重新预览；不修改系统权限" if request.mode == "software_test" else
                                "选择 MOCK 演示；真实适配需后续来源、工件及集成证据", field=field))

    if profile is None or profile.profile_id == "unknown":
        block("PROFILE_UNVERIFIED", "型号未确认，禁止映射到任何真实 SDK", "profile_id")
    elif request.mode == "mock" and profile.kind != "mock":
        block("MODE_PROFILE_MISMATCH", "真实型号不能隐式转换为 MOCK", "mode")
    elif request.mode == "software_test":
        if profile.kind != "software" or profile.profile_id != "ros-probe":
            block("MODE_PROFILE_MISMATCH", "真实软件测试只能选择 ROS 通信探针，不能替代 D1 适配", "profile_id")
        if not facts.docker_accessible:
            block("DOCKER_UNAVAILABLE", f"Docker 不可访问：{facts.docker_error or 'unknown'}", "docker_accessible")
        if not facts.compose_available:
            block("COMPOSE_UNAVAILABLE", "Compose v2 不可用或未取得", "compose_available")
        if facts.docker_os != "linux" or facts.docker_architecture not in {"x86_64", "aarch64"}:
            block("DOCKER_PLATFORM_UNVERIFIED", "未取得受支持的 Linux Docker 执行架构", "docker_os")
        if len(profile.artifact_requirements) != 1:
            block("ARTIFACT_UNAVAILABLE", "缺少本项目已构建并校验的 ROS 探针工件", "artifact_requirements")
        else:
            artifact = profile.artifact_requirements[0]
            if artifact.kind != "local_build" or artifact.source != "d1env/ros-probe":
                block("ARTIFACT_UNTRUSTED", "工件不是受信的本项目 ROS 探针构建", "artifact_requirements")
            if artifact.architecture != facts.docker_architecture:
                block("ARTIFACT_ARCHITECTURE_MISMATCH", "探针工件架构与 Docker 执行架构不符", "artifact_requirements")
    elif request.mode == "real_readonly":
        block("ADAPTER_UNAVAILABLE", "本轮只有 MOCK 执行器，真实只读适配尚未实现", "mode")
        if not profile.artifact_requirements:
            block("ARTIFACT_UNAVAILABLE", "缺少已校验的真实工件与不可变标识", "artifact_requirements")
        if profile.firmware_rules is None:
            block("FIRMWARE_UNVERIFIED", "固件兼容范围尚未验证", "firmware_rules")
    minimum_disk = profile.runtime_requirements.min_disk_bytes if profile else 104857600
    if facts.disk_free_bytes is None or facts.disk_free_bytes < minimum_disk:
        block("DISK_UNVERIFIED", f"项目磁盘未取得或低于此配置的软件阈值 {minimum_disk} 字节", "disk_free_bytes")
    if blockers or profile is None:
        return PlanResolution(blockers=blockers)
    software = request.mode == "software_test"
    operations = tuple(Operation(operation_id=opid, label=label,
                                 required_evidence=("mock_ready",) if opid.startswith("verify") else ())
                       for opid, label in [
                           ("preflight", "复核 MOCK 条件"), ("acquire", "模拟准备工件（没有真实下载）"),
                           ("configure", "建立本作业 MOCK 资源"), ("start", "模拟服务启动"),
                           ("verify_failure" if request.demo_scenario == "verify_failure" else "verify",
                            "故障注入：模拟就绪检查失败" if request.demo_scenario == "verify_failure" else "验证 MOCK 软件流程"),
                       ])
    if software:
        operations = tuple(Operation(
            operation_id=opid, kind="docker_step", label=label,
            artifact=profile.artifact_requirements[0], timeout_s=60.0,
            probe_scenario=request.probe_scenario,
            required_evidence=("software_ready",) if opid == "verify" else (),
        ) for opid, label in [
            ("preflight", "复核本地 Docker 与工件身份"),
            ("acquire", "校验已有真实 ROS 镜像（不伪造下载进度）"),
            ("configure", "生成本作业的受限容器配置"),
            ("start", "启动真实 ROS 软件测试服务"),
            ("verify", "故障注入：无发布者检查" if request.probe_scenario == "no_publisher"
             else "检查真实 ROS 消息与新鲜度（未接真机）"),
        ])
    config_digest = canonical_hash({"profile": profile.model_dump(mode="json"),
                                    "request": request.model_dump(mode="json"),
                                    "app_version": __version__,
                                    "host": {"os": facts.os_name, "version": facts.os_version, "architecture": facts.architecture},
                                    **({"docker": {"os": facts.docker_os, "architecture": facts.docker_architecture,
                                                   "version": facts.docker_version}} if software else {})})
    prototype = DeploymentPlan(plan_id="", mode=request.mode, target_id=request.target_id,
                               profile_id=profile.profile_id, operations=operations,
                               required_evidence=("software_ready",) if software else ("mock_ready",),
                               verified_scope="software" if software else "mock",
                               profile_revision=profile.profile_revision, config_digest=config_digest,
                               request=request)
    if software:
        prototype = prototype.model_copy(update={
            "directories": ("用户任务状态目录（不挂载到容器）",),
            "services": ("ROS 测试发布者", "ROS 测试订阅者"),
            "permissions": ("本地 Docker 操作权（高权限信任边界）", "仅本作业容器与内部网络"),
            "network": "project_internal",
        })
    return PlanResolution(plan=prototype.model_copy(update={"plan_id": canonical_hash(prototype.model_dump(mode="json"))}))
