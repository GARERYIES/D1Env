import json
import platform
import shutil
import socket
from pathlib import Path
from typing import Literal

from .models import CheckResult, CheckStatus, DeploymentRequest, HostFacts, utcnow
from .process import ProbeRunner

DOCKER_INFO = ("docker", "--context", "default", "info", "--format",
               '{"version":{{json .ServerVersion}},"os":{{json .OSType}},"architecture":{{json .Architecture}}}')
COMPOSE_VERSION = ("docker", "--context", "default", "compose", "version", "--short")


def inspect_host(target_id: str, runner: ProbeRunner) -> HostFacts:
    if target_id != "local":
        raise ValueError("only registered local execution target is allowed")
    docker = runner.run(DOCKER_INFO)
    compose = runner.run(COMPOSE_VERSION)
    error: Literal["missing", "daemon_stopped", "permission_denied", "timeout", "unknown"] | None = None
    if docker.timed_out:
        error = "timeout"
    elif docker.returncode is None:
        error = "missing"
    elif docker.returncode != 0:
        text = docker.stderr.lower()
        error = ("permission_denied" if "permission denied" in text else
                 "daemon_stopped" if "cannot connect" in text or "daemon" in text else "unknown")
    os_name = platform.system()
    if os_name == "Linux":
        try:
            os_version = platform.freedesktop_os_release().get("VERSION_ID")
        except OSError:
            os_version = None
    else:
        os_version = platform.mac_ver()[0] or platform.release()
    arch = {"arm64": "aarch64", "AMD64": "x86_64"}.get(platform.machine(), platform.machine())
    try:
        free = shutil.disk_usage(Path.cwd()).free
    except OSError:
        free = None
    try:
        interfaces = [name for _, name in socket.if_nameindex()]
    except OSError:
        interfaces = []
    metadata: dict[str, str] = {}
    if error is None:
        try:
            decoded = json.loads(docker.stdout)
            if isinstance(decoded, dict):
                metadata = {key: value for key, value in decoded.items()
                            if key in {"version", "os", "architecture"} and isinstance(value, str)}
        except (ValueError, TypeError):
            pass  # Missing metadata blocks real software plans; it never becomes a guessed platform.
    return HostFacts(
        os_name=os_name, os_version=os_version, architecture=arch,
        docker_available=error != "missing", docker_accessible=None if error == "timeout" else error is None,
        compose_available=None if compose.timed_out else compose.returncode == 0,
        disk_free_bytes=free,
        gpu_available=Path("/dev/nvidia0").exists() if os_name == "Linux" else None,
        checked_at=utcnow(), docker_error=error, interfaces=interfaces,
        docker_os=metadata.get("os"), docker_version=metadata.get("version"),
        docker_architecture={"amd64": "x86_64", "arm64": "aarch64"}.get(
            metadata.get("architecture", ""), metadata.get("architecture")),
    )


def diagnose(request: DeploymentRequest, facts: HostFacts) -> list[CheckResult]:
    checks: list[CheckResult] = []

    def add(code: str, status: CheckStatus, reason: str, remediation: str, **evidence: object) -> None:
        from pydantic import JsonValue, TypeAdapter
        checks.append(CheckResult(code=code, status=status, reason=reason, remediation=remediation,
                                  origin="local_probe", observed_at=facts.checked_at,
                                  evidence=TypeAdapter(dict[str, JsonValue]).validate_python(evidence)))

    supported = facts.os_name == "Linux" and facts.os_version == "22.04" and facts.architecture == "x86_64"
    if request.mode == "software_test":
        software_platform = facts.docker_os == "linux" and facts.docker_architecture in {"x86_64", "aarch64"}
        add("PLATFORM", "PASS" if software_platform else "UNKNOWN",
            "Linux Docker 软件测试平台已取得（未接真机）" if software_platform else "Docker 执行平台未取得，禁止真实软件部署",
            "检查本地 Docker Desktop/Engine；Mac 软件测试不替代全新 Ubuntu 安装验收",
            host_os=facts.os_name, docker_os=facts.docker_os, architecture=facts.docker_architecture)
    else:
        add("PLATFORM", "PASS" if supported else "WARN" if request.mode == "mock" else "FAIL",
            "首版真实运行平台匹配" if supported else "当前平台仅用于界面、计划与 MOCK 开发",
            "真实部署后续需经验证的 Ubuntu 22.04 x86_64；本轮只运行演示",
            os=facts.os_name, version=facts.os_version, architecture=facts.architecture)
    docker_status: CheckStatus = "PASS" if facts.docker_accessible else "UNKNOWN" if facts.docker_accessible is None else "WARN" if request.mode == "mock" else "FAIL"
    add("DOCKER", docker_status, "本机 Docker 入口只读检测通过" if facts.docker_accessible else f"Docker 未就绪：{facts.docker_error or 'unknown'}",
        "检查本地 Docker 安装、服务及权限；本工具不会改权限或启动 daemon",
        available=facts.docker_available, accessible=facts.docker_accessible, error=facts.docker_error,
        context="fixed local Unix entry")
    compose_status: CheckStatus = "PASS" if facts.compose_available else "UNKNOWN" if facts.compose_available is None else "WARN" if request.mode == "mock" else "FAIL"
    add("COMPOSE", compose_status, "Compose 版本只读检测通过" if facts.compose_available else "Compose 未取得或不可用",
        "MOCK 不需要 Compose；真实容器验证在 M3", available=facts.compose_available)
    disk_status: CheckStatus = "UNKNOWN" if facts.disk_free_bytes is None else "PASS" if facts.disk_free_bytes >= 104857600 else "FAIL"
    add("DISK", disk_status, "本地项目可用磁盘检查（软件阈值 100 MiB）", "确认项目磁盘空间；不自动清理数据", free_bytes=facts.disk_free_bytes)
    add("GPU", "SKIPPED", "CPU 演示与基础诊断不需要 GPU", "无需为本轮安装显卡驱动", available=facts.gpu_available)
    add("NETWORK", "SKIPPED", "只枚举本机接口，不探测任何机器人或远端", "本轮无需配置网卡", interfaces=facts.interfaces)
    add("ROBOT", "UNKNOWN", "未连接机器人，未取得电量、姿态或传感器数据", "真实只读适配属于 M4；不要用演示结果判断真机状态", battery_percent=None, pose=None)
    return checks
