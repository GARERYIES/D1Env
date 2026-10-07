"""Fixed native Mac operations, preserving Apple's user-controlled security UI."""

import ctypes
import errno
import hashlib
import os
import plistlib
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from d1env.models import JSONValue
from d1env.runtime import ensure_private_state_dir

from .download import InstallerDownloader
from .models import TASK_ID, SetupError, validate_installer_lock

SIGNATURE_REQUIREMENT = (
    '=identifier "com.docker.docker" and anchor apple generic '
    'and certificate leaf[subject.OU] = "9BNSXJN65R"'
)


@dataclass(frozen=True)
class NativeResult:
    returncode: int | None
    timed_out: bool


class NativeRunner(Protocol):
    def run(self, argv: tuple[str, ...], cancel: threading.Event,
            timeout_s: float = 60) -> NativeResult: ...


class BoundedNativeRunner:
    def run(self, argv: tuple[str, ...], cancel: threading.Event,
            timeout_s: float = 60) -> NativeResult:
        if (not argv or argv[0] not in {"/usr/bin/hdiutil", "/usr/bin/codesign", "/usr/sbin/spctl",
                                        "/usr/bin/ditto", "/usr/bin/open"}
                or not 0 < timeout_s <= 300):
            raise SetupError("NATIVE_OPERATION_REJECTED", "原生准备操作不在固定白名单",
                             "使用完整发行包，不接受网页提供的命令")
        if cancel.is_set():
            raise SetupError("SETUP_CANCELLED", "用户取消了原生准备步骤", "可稍后继续准备")
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("DYLD_", "DOCKER_", "COMPOSE_"))}
        # No output is logged, and inherited Web/backend credentials are not supplied.
        env = {key: value for key, value in env.items()
               if not key.startswith(("D1ENV_", "PYTHON"))}
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                process = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=err, env=env, start_new_session=True)
            except OSError as exc:
                raise SetupError("NATIVE_OPERATION_FAILED", "无法执行系统原生安装检查",
                                 "检查 macOS 安全设置及应用安装权限",
                                 {"exception_type": type(exc).__name__}) from exc
            deadline = time.monotonic() + timeout_s
            timed_out = False
            while process.poll() is None:
                if cancel.is_set() or time.monotonic() >= deadline:
                    timed_out = not cancel.is_set()
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    if cancel.is_set():
                        raise SetupError("SETUP_CANCELLED", "用户取消了原生准备步骤",
                                         "已经安装的 Docker 将保留；不会停止已有服务或卸载应用")
                    break
                cancel.wait(0.05)
            return NativeResult(None if timed_out else process.returncode, timed_out)


def _rename_exclusive(source: Path, destination: Path) -> None:
    """macOS RENAME_EXCL (SDK sys/stdio.h = 0x4) refuses every existing destination."""
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    rename = library.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(os.fsencode(source), os.fsencode(destination), 0x00000004) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


class MacInstaller:
    def __init__(self, cache_dir: Path, *, runner: NativeRunner | None = None,
                 applications_dir: Path = Path("/Applications"),
                 writable: Callable[[Path], bool] | None = None,
                 renamer: Callable[[Path, Path], None] | None = None):
        self.cache_dir = ensure_private_state_dir(cache_dir.absolute())
        self.runner = runner or BoundedNativeRunner()
        self.applications_dir = applications_dir.absolute()
        self.app = self.applications_dir / "Docker.app"
        self.writable = writable or (lambda path: os.access(path, os.W_OK))
        self.renamer = renamer or _rename_exclusive

    def app_exists(self) -> bool:
        return self.app.exists() or self.app.is_symlink()

    @staticmethod
    def _check_app(app: Path) -> dict[str, JSONValue]:
        for item in (*reversed(app.parents), app):
            if item.is_symlink():
                raise SetupError("INSTALLER_APP_UNSAFE", "Docker 应用路径包含符号链接",
                                 "检查原有应用位置；D1Env 不覆盖或绕过链接安装")
        if not app.is_dir():
            raise SetupError("INSTALLER_APP_MISSING", "尚未找到 Docker.app",
                             "在系统安装窗口完成安装后返回点击重新检查")
        count = 0
        fingerprint = hashlib.sha256()
        pending = [app]
        while pending:
            item = pending.pop()
            try:
                observed = item.lstat()
                count += 1
                if count > 100000 or observed.st_uid not in {0, os.getuid()}:
                    raise ValueError("untrusted owner or oversized application tree")
                target = ""
                if stat.S_ISLNK(observed.st_mode):
                    # Framework aliases and dylib links are legitimate, but only inside this bundle.
                    target = os.readlink(item)
                    item.resolve(strict=True).relative_to(app)
                elif stat.S_ISREG(observed.st_mode) or stat.S_ISDIR(observed.st_mode):
                    if observed.st_mode & (stat.S_IWOTH | stat.S_IWGRP):
                        raise ValueError("group or world writable application entry")
                    if stat.S_ISREG(observed.st_mode) and observed.st_nlink != 1:
                        raise ValueError("hard-linked application file")
                    if stat.S_ISDIR(observed.st_mode):
                        # Never recurse through symlinks; their resolved target is already in this tree.
                        pending.extend(sorted(item.iterdir(), key=lambda entry: entry.name))
                else:
                    raise ValueError("application entry is not a directory, file or internal symlink")
                identity = (str(item.relative_to(app)), observed.st_dev, observed.st_ino,
                            observed.st_mode, observed.st_uid, observed.st_gid, observed.st_nlink,
                            observed.st_size, observed.st_mtime_ns, observed.st_ctime_ns, target)
                fingerprint.update(repr(identity).encode("utf-8"))
            except (OSError, RuntimeError, ValueError) as exc:
                raise SetupError("INSTALLER_APP_UNSAFE", "Docker 应用内部归属、权限或资源链接异常",
                                 "保留原有应用，检查官方安装来源；不会放宽权限或运行不可信启动文件") from exc
        info = app / "Contents/Info.plist"
        if info.is_symlink() or not info.is_file() or info.stat().st_size > 1024**2:
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 应用身份文件异常", "不要运行此应用，检查官方来源")
        try:
            metadata = plistlib.loads(info.read_bytes())
        except (ValueError, OSError, plistlib.InvalidFileException) as exc:
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 应用身份无法读取", "检查官方安装来源") from exc
        if not isinstance(metadata, dict) or metadata.get("CFBundleIdentifier") != "com.docker.docker":
            raise SetupError("INSTALLER_APP_UNSAFE", "应用不是官方 Docker Desktop 身份", "保留原有文件并检查安装来源")
        # Read-only audit of the pinned official 4.80.0 bundle identifies this exact main executable.
        if metadata.get("CFBundleExecutable") != "com.docker.backend":
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 主启动文件身份不匹配当前核验范围",
                             "保留原有安装，使用当前支持的官方 Docker Desktop；不执行任意 plist 启动路径")
        executable = app / "Contents/MacOS/com.docker.backend"
        try:
            main = executable.lstat()
        except OSError as exc:
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 主启动文件缺失", "检查完整官方安装包") from exc
        if (not stat.S_ISREG(main.st_mode) or main.st_uid not in {0, os.getuid()}
                or main.st_nlink != 1 or main.st_mode & 0o022 or not os.access(executable, os.X_OK)):
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 主启动文件权限或类型异常",
                             "不要运行此应用，检查完整官方安装来源")
        return {"version": str(metadata.get("CFBundleShortVersionString", "")),
                "build": str(metadata.get("CFBundleVersion", "")), "executable": "com.docker.backend",
                "permission_tree_verified": True, "app_entries_checked": count,
                "security_metadata_sha256": fingerprint.hexdigest()}

    def _run(self, argv: tuple[str, ...], cancel: threading.Event, *, code: str,
             message: str, timeout_s: float = 60) -> None:
        if cancel.is_set():
            raise SetupError("SETUP_CANCELLED", "用户取消了环境准备", "已经安装的应用将保留")
        result = self.runner.run(argv, cancel, timeout_s)
        if cancel.is_set():
            raise SetupError("SETUP_CANCELLED", "用户取消了环境准备", "已经安装的应用将保留")
        if result.returncode != 0 or result.timed_out:
            raise SetupError(code, message, "在 macOS 原生窗口检查安全设置或权限后重试；不关闭 Gatekeeper",
                             {"exit_code": result.returncode, "timed_out": result.timed_out})

    def _verify_app(self, app: Path, cancel: threading.Event) -> dict[str, JSONValue]:
        info = self._check_app(app)
        self._run(("/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
                   "--test-requirement", SIGNATURE_REQUIREMENT, str(app)), cancel,
                  code="INSTALLER_SIGNATURE_REJECTED", message="Docker 官方签名或 Team ID 校验失败", timeout_s=90)
        self._run(("/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=2", str(app)), cancel,
                  code="INSTALLER_GATEKEEPER_REJECTED", message="macOS Gatekeeper 未放行 Docker 应用", timeout_s=90)
        current = self._check_app(app)
        if current["security_metadata_sha256"] != info["security_metadata_sha256"]:
            raise SetupError("INSTALLER_APP_UNSAFE", "Docker 应用在系统核验过程中发生变化",
                             "保留原有应用并重新检查；不会沿用旧签名结果运行已变化的启动文件")
        return {**info, "signature_verified": True, "gatekeeper_verified": True}

    def install(self, dmg: Path, lock: dict[str, JSONValue], task_id: str,
                cancel: threading.Event) -> dict[str, JSONValue]:
        validate_installer_lock(lock)
        if not TASK_ID.fullmatch(task_id):
            raise SetupError("SETUP_TASK_ID_INVALID", "准备任务 ID 不合法", "使用已创建的准备任务")
        if self.app_exists():
            return {"installed": False, "reused_existing": True, "existing_app_preserved": True}
        if dmg != self.cache_dir / (str(lock["sha256"]) + ".dmg"):
            raise SetupError("INSTALLER_PATH_REJECTED", "安装包不是本任务校验缓存", "重新准备官方安装包")
        InstallerDownloader.verify(dmg, lock, cancel)
        mounts = ensure_private_state_dir(self.cache_dir / "mounts")
        mount = Path(tempfile.mkdtemp(prefix=f"{task_id}-", dir=mounts))
        staging: Path | None = None
        mounted = False
        native_handoff: dict[str, JSONValue] | None = None
        try:
            mounted = True
            self._run(("/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(dmg)),
                      cancel, code="INSTALLER_MOUNT_FAILED", message="Docker 安装包只读挂载失败", timeout_s=120)
            app = mount / "Docker.app"
            evidence = self._verify_app(app, cancel)
            if evidence["version"] != lock["version"] or evidence["build"] != lock["build"]:
                raise SetupError("INSTALLER_VERSION_MISMATCH", "下载应用版本与来源锁不符", "不要安装此文件，检查官方来源")
            if self.app_exists():
                return {**evidence, "installed": False, "reused_existing": True, "existing_app_preserved": True}
            if not self.writable(self.applications_dir):
                # Complete our read-only mount cleanup before Finder can reuse the image.
                native_handoff = {**evidence, "installed": False, "native_setup_required": True,
                                  "system_authorization": "user_controlled", "existing_app_preserved": True}
            else:
                # Copy into a unique owned staging directory; commit never replaces an existing app.
                staging = Path(tempfile.mkdtemp(prefix=f".d1env-docker-{task_id}-", dir=self.applications_dir))
                copied = staging / "Docker.app"
                self._run(("/usr/bin/ditto", "--rsrc", "--extattr", str(app), str(copied)), cancel,
                          code="INSTALLER_COPY_FAILED", message="复制 Docker 应用失败", timeout_s=300)
                self._verify_app(copied, cancel)
                if cancel.is_set():
                    raise SetupError("SETUP_CANCELLED", "用户取消了应用安装", "可稍后重新准备")
                try:
                    self.renamer(copied, self.app)
                except OSError as exc:
                    if exc.errno in {errno.EEXIST, errno.ENOTEMPTY} or self.app_exists():
                        raise SetupError("EXISTING_DOCKER_PRESERVED", "安装时发现已有 Docker，保留原有应用",
                                         "点击重新检查以复用已有 Docker；不会覆盖或自动升级") from exc
                    raise
                return {**evidence, "installed": True, "reused_existing": False,
                        "system_authorization": "user_controlled", "quarantine_removed": False,
                        "extended_attributes_preserved_by_ditto": True}
        except OSError as exc:
            raise SetupError("INSTALLER_COPY_FAILED", "原生应用安装未完成",
                             "检查应用目录权限后重试；不使用 sudo 或收集系统密码",
                             {"exception_type": type(exc).__name__}) from exc
        finally:
            if staging is not None:
                shutil.rmtree(staging)  # Only this process's unique staging directory.
            if mounted:
                # Cleanup must run even after cancellation; never force-detach any other volume.
                detached = self.runner.run(("/usr/bin/hdiutil", "detach", str(mount)), threading.Event(), 60)
                if detached.returncode != 0 or detached.timed_out:
                    raise SetupError("INSTALLER_UNMOUNT_FAILED", "Docker 安装盘的只读卸载未完成",
                                     "保留已安装应用及安装盘；在 macOS 中手动推出本任务安装盘后重新检查",
                                     {"exit_code": detached.returncode, "timed_out": detached.timed_out,
                                      "owned_mount_only": True, "application_preserved": True})
            try:
                mount.rmdir()
            except OSError:
                pass  # A failed unmount is preserved, never recursively removed.
        if native_handoff is None:
            raise AssertionError("native installer handoff is missing")
        self._run(("/usr/bin/open", str(dmg)), cancel, code="INSTALLER_NATIVE_UI_FAILED",
                  message="无法打开系统安装窗口")
        return native_handoff

    def start(self, lock: dict[str, JSONValue], cancel: threading.Event) -> dict[str, JSONValue]:
        validate_installer_lock(lock)
        evidence = self._verify_app(self.app, cancel)
        self._run(("/usr/bin/open", "-a", str(self.app)), cancel,
                  code="INSTALLER_START_FAILED", message="无法打开 Docker Desktop")
        return {**evidence, "opened_application": True, "accept_license_flag": False,
                "changed_system_configuration": False}
