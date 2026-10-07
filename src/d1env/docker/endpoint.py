"""Select fixed local Docker entry points without modifying global settings."""

import os
import platform
import shutil
import stat
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REQUIREMENT = ('=identifier "com.docker.docker" and anchor apple generic '
               'and certificate leaf[subject.OU] = "9BNSXJN65R"')
_signature_lock = threading.RLock()
_verified: dict[str, tuple[tuple[object, ...], ...]] = {}


@dataclass(frozen=True)
class LocalDockerEndpoint:
    prefix: tuple[str, ...]
    plugin_dir: Path | None
    local: bool

    def __post_init__(self) -> None:
        default = self.prefix == ("docker", "--context", "default")
        desktop = (len(self.prefix) == 3 and self.prefix[1] == "--host"
                   and self.prefix[2].startswith("unix:///")
                   and self.prefix[2].endswith("/.docker/run/docker.sock")
                   and Path(self.prefix[0]).is_absolute()
                   and Path(self.prefix[0]).parts[-5:] ==
                   ("Docker.app", "Contents", "Resources", "bin", "docker")
                   and ".." not in Path(self.prefix[2][7:]).parts)
        if not (default or desktop) or self.local is not True:
            raise ValueError("DOCKER_ENDPOINT_UNSAFE: 只接受已核验的本机 Docker 入口。")


def verify_desktop_app(app: Path) -> None:
    with _signature_lock:
        try:
            _verify_desktop_app(app)
        except (OSError, RuntimeError) as exc:
            raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用在核验期间缺失或资源链接异常。") from exc


def _application_fingerprint(app: Path) -> tuple[tuple[object, ...], ...]:
    for directory in (*reversed(app.parents), app):
        if directory.is_symlink():
            raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用路径不能重定向。")
    observed_app = app.lstat()
    if (not stat.S_ISDIR(observed_app.st_mode) or observed_app.st_uid not in {0, os.getuid()}
            or observed_app.st_mode & 0o022):
        raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用目录归属或权限异常。")
    paths = [app / "Contents/Info.plist", app / "Contents/Resources/bin/docker",
             app / "Contents/_CodeSignature/CodeResources"]
    plugin = app / "Contents/Resources/cli-plugins/docker-compose"
    if plugin.is_file():
        paths.append(plugin)
    fingerprint: list[tuple[object, ...]] = []
    for path in paths:
        try:
            observed = path.lstat()
        except OSError as exc:
            raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用不完整；请重新准备官方运行环境。") from exc
        if (not stat.S_ISREG(observed.st_mode) or observed.st_uid not in {0, os.getuid()}
                or observed.st_mode & 0o022):
            raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用文件归属或权限异常。")
        for directory in path.parents:
            if directory == app.parent:
                break
            item = directory.lstat()
            if (not stat.S_ISDIR(item.st_mode) or item.st_uid not in {0, os.getuid()} or item.st_mode & 0o022):
                raise ValueError("DOCKER_APP_UNVERIFIED: Docker 命令路径归属或权限异常。")
    # Every component participates, including directory permissions and ctime;
    # changing an executable outside the CLI must invalidate the signature cache.
    for root, directories, files in os.walk(app, followlinks=False):
        directories.sort()
        for name in [".", *sorted(directories), *sorted(files)]:
            path = Path(root) / name
            item = path.lstat()
            if item.st_uid not in {0, os.getuid()}:
                raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用内部文件归属异常。")
            if stat.S_ISLNK(item.st_mode):
                if not path.resolve(strict=True).is_relative_to(app):
                    raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用资源链接越出应用目录。")
            elif stat.S_ISDIR(item.st_mode) or stat.S_ISREG(item.st_mode):
                if item.st_mode & 0o022 or (stat.S_ISREG(item.st_mode) and item.st_nlink != 1):
                    raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用内部权限或链接异常。")
            else:
                raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用内部文件类型异常。")
            fingerprint.append((str(path), item.st_ino, item.st_mtime_ns, item.st_ctime_ns,
                                item.st_size, item.st_mode, item.st_uid, item.st_gid, item.st_nlink))
            if len(fingerprint) > 100000:
                raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用文件数量异常。")
    return tuple(fingerprint)


def _verify_desktop_app(app: Path) -> None:
    key = _application_fingerprint(app)
    if _verified.get(str(app)) == key:
        return
    for argv in [
        ("/usr/bin/codesign", "--verify", "--deep", "--strict", "-R", REQUIREMENT, str(app)),
        ("/usr/sbin/spctl", "--assess", "--type", "execute", str(app)),
    ]:
        try:
            result = subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False, shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("DOCKER_APP_UNVERIFIED: 无法核对官方签名或系统运行许可；请完成系统确认后重试。") from exc
        if result.returncode != 0:
            raise ValueError("DOCKER_APP_UNVERIFIED: 官方签名或 Gatekeeper 核验未通过；不会绕过系统检查。")
    if _application_fingerprint(app) != key:
        raise ValueError("DOCKER_APP_UNVERIFIED: Docker 应用在签名核验期间发生变化，未执行命令。")
    _verified[str(app)] = key


def resolve_endpoint(*, system: str | None = None,
                     which: Callable[[str], str | None] = shutil.which,
                     home: Path | None = None, app_path: Path | None = None,
                     verify_app: Callable[[Path], None] = verify_desktop_app,
                     default_socket: Path = Path("/var/run/docker.sock")) -> LocalDockerEndpoint:
    """Inputs are trusted local adapters/tests, never supplied by HTTP requests."""
    if (system or platform.system()) != "Darwin":
        return LocalDockerEndpoint(("docker", "--context", "default"), None, True)
    app = app_path or Path("/Applications/Docker.app")
    if not app.exists() and not app.is_symlink():
        if which("docker") is not None:
            raise ValueError("DOCKER_APP_UNVERIFIED: 此 Mac Docker 入口尚未核验；不运行 PATH 中的未知命令。")
        return LocalDockerEndpoint(("docker", "--context", "default"), None, True)
    verify_app(app)
    cli = app / "Contents/Resources/bin/docker"
    if cli.is_symlink() or not cli.is_file() or not os.access(cli, os.X_OK):
        raise ValueError("DOCKER_APP_UNVERIFIED: 缺少可信 Docker 命令入口。")
    socket = (home or Path.home()) / ".docker/run/docker.sock"
    for ancestor in [socket.parent.parent, socket.parent]:
        if ancestor.is_symlink():
            raise ValueError("DOCKER_ENDPOINT_UNSAFE: 本机 Docker 连接目录不能重定向。")
        if ancestor.exists():
            observed = ancestor.lstat()
            if (not stat.S_ISDIR(observed.st_mode) or observed.st_uid != os.getuid()
                    or observed.st_mode & 0o022):
                raise ValueError("DOCKER_ENDPOINT_UNSAFE: 本机 Docker 连接目录归属或权限异常。")
    if socket.exists() or socket.is_symlink():
        observed = socket.lstat()
        if (not stat.S_ISSOCK(observed.st_mode) or observed.st_uid != os.getuid()
                or observed.st_mode & 0o002):
            raise ValueError("DOCKER_ENDPOINT_UNSAFE: 本机 Docker 连接不是当前用户的 Unix socket。")
    plugins = app / "Contents/Resources/cli-plugins"
    return LocalDockerEndpoint((str(cli), "--host", f"unix://{socket}"),
                               plugins if plugins.is_dir() else None, True)
