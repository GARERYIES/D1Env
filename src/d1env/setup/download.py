"""Bounded verified official download; no TLS bypass or arbitrary redirects."""

import hashlib
import http.client
import os
import shutil
import ssl
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import IO, Protocol, cast

from d1env.models import JSONValue
from d1env.runtime import ensure_private_state_dir

from .models import SetupError, validate_descriptor, validate_installer_lock, validate_private_file


class DownloadResponse(Protocol):
    @property
    def status(self) -> int: ...

    def geturl(self) -> str: ...
    def read(self, count: int = -1) -> bytes: ...
    def close(self) -> None: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int,
                         msg: str, headers: object, newurl: str) -> None:
        raise SetupError("INSTALLER_REDIRECT_REJECTED", "安装下载出现未锁定的跳转",
                         "检查网络或使用经核验的新发行包；不会降低 TLS 校验")


class _SingleReceiveHTTP:
    """HTTPResponse.read1 performs at most one underlying receive per iteration."""

    def __init__(self, response: http.client.HTTPResponse):
        self.response = response

    @property
    def status(self) -> int:
        return self.response.status

    def geturl(self) -> str:
        return self.response.geturl()

    def read(self, count: int = -1) -> bytes:
        return self.response.read1(count)

    def close(self) -> None:
        self.response.close()


def _open_official(url: str) -> DownloadResponse:
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    return _SingleReceiveHTTP(cast(http.client.HTTPResponse, opener.open(url, timeout=15)))


class InstallerDownloader:
    def __init__(self, cache_dir: Path, *, opener: Callable[[str], DownloadResponse] = _open_official,
                 free_space: Callable[[Path], int] | None = None,
                 download_timeout_s: float = 1800, clock: Callable[[], float] = time.monotonic):
        if (type(download_timeout_s) not in {int, float}
                or not 0 < download_timeout_s <= 3600):
            raise ValueError("bounded download deadline required: 0 < timeout <= 3600 seconds")
        self.cache_dir = ensure_private_state_dir(cache_dir.absolute())
        self.opener = opener
        self.free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self.download_timeout_s = download_timeout_s
        self.clock = clock

    def _check_deadline(self, deadline: float) -> None:
        if self.clock() >= deadline:
            raise SetupError("INSTALLER_DOWNLOAD_TIMEOUT", "官方 Docker 安装包下载超过整体时限",
                             "检查网络后显式重试；本任务片段不会被当作完整安装包",
                             {"timeout_seconds": self.download_timeout_s})

    @staticmethod
    def verify(path: Path, lock: dict[str, JSONValue], cancel: threading.Event) -> None:
        validate_installer_lock(lock)
        validate_private_file(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            validate_descriptor(descriptor)
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                while chunk := stream.read(1024**2):
                    if cancel.is_set():
                        raise SetupError("SETUP_CANCELLED", "用户取消了运行环境准备", "可稍后重新准备")
                    count += len(chunk)
                    digest.update(chunk)
            if count != lock["size_bytes"]:
                raise SetupError("INSTALLER_SIZE_MISMATCH", "Docker 安装包字节数与来源锁不符",
                                 "保留错误证据，删除本任务缓存后重新下载官方版本",
                                 {"expected_bytes": lock["size_bytes"], "actual_bytes": count})
            if digest.hexdigest() != lock["sha256"]:
                raise SetupError("INSTALLER_HASH_MISMATCH", "Docker 安装包 SHA-256 校验失败",
                                 "不要打开此文件；检查网络与磁盘，重新取得官方发行包")
        finally:
            os.close(descriptor)

    def fetch(self, lock: dict[str, JSONValue], cancel: threading.Event,
              progress: Callable[[int, int], None]) -> Path:
        validate_installer_lock(lock)
        size = cast(int, lock["size_bytes"])
        final = self.cache_dir / (cast(str, lock["sha256"]) + ".dmg")
        partial = self.cache_dir / (cast(str, lock["sha256"]) + ".part")
        if cancel.is_set():
            raise SetupError("SETUP_CANCELLED", "用户取消了运行环境准备", "可稍后重新准备")
        if final.exists() or final.is_symlink():
            try:
                self.verify(final, lock, cancel)
            except SetupError as exc:
                if exc.code in {"INSTALLER_HASH_MISMATCH", "INSTALLER_SIZE_MISMATCH"}:
                    # The name is in this private cache; validation already excluded links/other owners.
                    validate_private_file(final)
                    final.unlink()
                raise
            progress(size, size)
            return final
        validate_private_file(partial, missing_ok=True)
        if self.free_space(self.cache_dir) < size * 2 + 512 * 1024**2:
            raise SetupError("INSTALLER_DISK_SPACE", "下载与安装所需磁盘空间不足",
                             "释放用户自己的空间后重试；D1Env 不自动删除镜像或其他数据")
        response: DownloadResponse | None = None
        descriptor: int | None = None
        started = self.clock()
        deadline = started + self.download_timeout_s
        last_progress = started
        reported_bytes = 0
        try:
            response = self.opener(cast(str, lock["url"]))
            self._check_deadline(deadline)
            if response.geturl() != lock["url"] or response.status != 200:
                raise SetupError("INSTALLER_REDIRECT_REJECTED", "安装包响应不是锁定的官方 HTTPS 地址",
                                 "检查网络；不会关闭 TLS 校验或接受替代域名")
            descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            validate_descriptor(descriptor)
            os.ftruncate(descriptor, 0)  # Partial content is never trusted as resumed content.
            done = 0
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                while True:
                    if cancel.is_set():
                        raise SetupError("SETUP_CANCELLED", "用户取消了运行环境下载", "可重新准备；残留片段不会被当作完整安装包")
                    self._check_deadline(deadline)
                    chunk = response.read(min(1024**2, size - done + 1))
                    self._check_deadline(deadline)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > size:
                        raise SetupError("INSTALLER_SIZE_MISMATCH", "下载超出锁定的安装包大小",
                                         "不要打开此文件，检查官方来源与网络")
                    stream.write(chunk)
                    observed = self.clock()
                    if done == size or done - reported_bytes >= 1024**2 or observed - last_progress >= 0.25:
                        progress(done, size)
                        last_progress, reported_bytes = observed, done
                stream.flush()
                os.fsync(descriptor)
            self._check_deadline(deadline)
            self.verify(partial, lock, cancel)
            self._check_deadline(deadline)
            if final.exists() or final.is_symlink():
                raise SetupError("INSTALLER_CACHE_CONFLICT", "安装缓存出现并发冲突", "等待现有准备任务结束后重试")
            # A hard link creates the final name without replacing any raced-in file.
            os.link(partial, final, follow_symlinks=False)
            partial.unlink()
            validate_private_file(final)
            return final
        except (OSError, urllib.error.URLError) as exc:
            if isinstance(exc, SetupError):
                raise
            raise SetupError("INSTALLER_DOWNLOAD_FAILED", "官方 Docker 安装包下载失败",
                             "检查网络、证书或磁盘后重试；TLS 校验保持开启",
                             {"exception_type": type(exc).__name__}) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if response is not None:
                response.close()
