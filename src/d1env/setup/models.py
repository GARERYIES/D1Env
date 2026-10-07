"""Strict first-run task contracts and trusted installer identity."""

import os
import re
import stat
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field

from d1env.models import JSONValue, StrictModel

SetupState = Literal["RUNNING", "WAITING_USER", "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"]
SetupStage = Literal[
    "detect", "license", "download", "verify", "install", "native_setup", "start",
    "wait_ready", "import_image", "complete",
]
SetupAction = Literal["accept_license", "check_again"]
TASK_ID = re.compile(r"^[0-9a-f]{32}$")
REQUEST_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")


class SetupError(ValueError):
    def __init__(self, code: str, message: str, remediation: str,
                 evidence: dict[str, JSONValue] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.remediation = remediation
        self.evidence = evidence or {}


class SetupTask(StrictModel):
    task_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    request_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
    scope: Literal["runtime_environment"] = "runtime_environment"
    state: SetupState = "RUNNING"
    stage: SetupStage = "detect"
    message: str
    remediation: str = ""
    user_action: SetupAction | None = None
    environment_ready: bool | None = None
    events: list[dict[str, JSONValue]] = Field(default_factory=list)
    evidence: dict[str, JSONValue] = Field(default_factory=dict)
    error: dict[str, JSONValue] | None = None
    error_code: str | None = None
    progress: dict[str, JSONValue] | None = None
    license_accepted: bool = False
    created_at: str
    updated_at: str


def validate_installer_lock(lock: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """A release-owned data lock, never an arbitrary Web URL or command."""
    url = lock.get("url")
    sha = lock.get("sha256")
    size = lock.get("size_bytes")
    build = lock.get("build")
    version = lock.get("version")
    minimum = lock.get("minimum_macos")
    parts = urlsplit(url) if isinstance(url, str) else None
    valid = (
        lock.get("schema_version") == 1
        and lock.get("kind") == "d1env_docker_desktop_installer"
        and lock.get("retrieval_status") == "verified"
        and lock.get("platform") == "macos" and lock.get("architecture") == "aarch64"
        and lock.get("team_id") == "9BNSXJN65R" and lock.get("bundle_id") == "com.docker.docker"
        and isinstance(build, str) and bool(re.fullmatch(r"[0-9]{1,9}", build))
        and isinstance(version, str) and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version))
        and isinstance(minimum, str) and bool(re.fullmatch(r"[0-9]+\.[0-9]+", minimum))
        and isinstance(sha, str) and bool(re.fullmatch(r"[0-9a-f]{64}", sha))
        and sha != "0" * 64 and type(size) is int and 0 < size <= 2 * 1024**3
        and parts is not None and parts.scheme == "https" and parts.netloc == "desktop.docker.com"
        and parts.path == f"/mac/main/arm64/{build}/Docker.dmg"
        and not parts.query and not parts.fragment
        and lock.get("license_url") == "https://www.docker.com/legal/docker-subscription-service-agreement/"
    )
    if not valid:
        raise SetupError("INSTALLER_SOURCE_BLOCKED", "Docker 安装来源锁缺失或身份校验失败",
                         "使用完整的 D1Env 发行包；不接受自行填写下载网址或安装命令")
    return lock


def validate_private_file(path: Path, *, missing_ok: bool = False) -> None:
    try:
        item = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return
        raise
    if (not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or item.st_nlink != 1
            or item.st_mode & 0o077):
        raise SetupError("SETUP_FILE_UNSAFE", "首次准备状态或缓存文件归属、权限或链接异常",
                         "保留现有数据，检查用户私有状态目录；不要放宽文件权限")


def validate_descriptor(descriptor: int) -> None:
    item = os.fstat(descriptor)
    if (not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or item.st_nlink != 1
            or item.st_mode & 0o077):
        raise SetupError("SETUP_FILE_UNSAFE", "首次准备文件在打开时校验失败",
                         "检查用户私有状态目录，拒绝链接或共享文件")
