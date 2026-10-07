"""Trusted offline *data* bundles; never installers or arbitrary Docker layers."""

import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import unicodedata
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from .runtime import ensure_private_state_dir

MANIFEST_NAME = "d1env-offline.json"
MANIFEST_LIMIT = 65536
CHUNK_SIZE = 65536


@dataclass(frozen=True)
class OfflineFile:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ValidatedOfflineArchive:
    archive_path: Path
    destination: Path
    sha256: str
    bundle_id: str
    files: tuple[OfflineFile, ...]
    total_bytes: int


@dataclass(frozen=True)
class _Member:
    name: str
    size: int
    is_dir: bool
    original: zipfile.ZipInfo | tarfile.TarInfo


def _digest(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) or value == "0" * 64:
        raise ValueError("DIGEST_REQUIRED: 必须由可信来源明确提供非占位 SHA-256")
    return value


def _hash(stream: BinaryIO) -> str:
    stream.seek(0)
    value = hashlib.sha256()
    while chunk := stream.read(CHUNK_SIZE):
        value.update(chunk)
    stream.seek(0)
    return value.hexdigest()


def _safe_name(name: str) -> str:
    clean = name.rstrip("/")
    if (not clean or clean.startswith("/") or "\\" in clean or ":" in clean
            or any(ord(character) < 32 for character in clean)
            or any(part in {"", ".", ".."} for part in clean.split("/"))):
        raise ValueError("ARCHIVE_PATH_INVALID: 归档路径不能跳出数据目录或使用异常路径")
    return clean


def _filename_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("MANIFEST_DUPLICATE: JSON 字段不能重复")
        result[key] = value
    return result


def _manifest(raw: bytes) -> tuple[str, tuple[OfflineFile, ...]]:
    try:
        value = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("MANIFEST_INVALID: 数据清单不是有效 UTF-8 JSON") from exc
    if (not isinstance(value, dict)
            or set(value) != {"schema_version", "kind", "bundle_id", "files"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["kind"] != "d1env_data_bundle"
            or not isinstance(value["bundle_id"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value["bundle_id"])
            or not isinstance(value["files"], list) or not value["files"]):
        raise ValueError("MANIFEST_INVALID: 仅支持严格的 D1Env 数据包，不接受安装器或 Docker save 清单")
    files: list[OfflineFile] = []
    seen: set[str] = set()
    for item in value["files"]:
        if (not isinstance(item, dict) or set(item) != {"path", "size_bytes", "sha256"}
                or not isinstance(item["path"], str) or type(item["size_bytes"]) is not int
                or item["size_bytes"] < 0):
            raise ValueError("MANIFEST_INVALID: 文件清单字段或大小无效")
        name = _safe_name(item["path"])
        if not name.startswith("payload/"):
            raise ValueError("ARCHIVE_PATH_INVALID: 数据文件必须位于 payload/，不能覆盖安装资源")
        folded = _filename_key(name)
        if folded in seen:
            raise ValueError("ARCHIVE_DUPLICATE: 数据文件名重复或大小写冲突")
        seen.add(folded)
        files.append(OfflineFile(name, item["size_bytes"], _digest(item["sha256"])))
    return value["bundle_id"], tuple(files)


def _members(reader: zipfile.ZipFile | tarfile.TarFile, max_members: int,
             max_member_bytes: int, max_total_bytes: int) -> list[_Member]:
    result: list[_Member] = []
    seen: set[str] = set()
    total = 0
    entries = reader.infolist() if isinstance(reader, zipfile.ZipFile) else iter(reader)
    for item in entries:
        if len(result) >= max_members:
            raise ValueError("ARCHIVE_CAPACITY: 归档成员数量超过限制")
        if isinstance(item, zipfile.ZipInfo):
            name = _safe_name(item.filename)
            kind = stat.S_IFMT(item.external_attr >> 16)
            is_dir = item.is_dir()
            if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or item.flag_bits & 1:
                raise ValueError("ARCHIVE_TYPE_INVALID: 不接受链接、特殊文件或加密归档")
            size = item.file_size
        else:
            name = _safe_name(item.name)
            is_dir = item.isdir()
            if not (item.isfile() or is_dir) or item.sparse is not None:
                raise ValueError("ARCHIVE_TYPE_INVALID: 不接受符号链接、硬链接、稀疏或特殊文件")
            size = item.size
        if size < 0 or (is_dir and size != 0):
            raise ValueError("ARCHIVE_TYPE_INVALID: 目录或成员大小无效")
        allowed_size = MANIFEST_LIMIT if name == MANIFEST_NAME else max_member_bytes
        if size > allowed_size:
            raise ValueError("ARCHIVE_CAPACITY: 在读取或跳过成员前拒绝超大数据")
        if name != MANIFEST_NAME:
            total += size
            if total > max_total_bytes:
                raise ValueError("ARCHIVE_CAPACITY: 归档累计解压大小超过限制")
        if _filename_key(name) in seen:
            raise ValueError("ARCHIVE_DUPLICATE: 成员名称重复或大小写冲突")
        seen.add(_filename_key(name))
        result.append(_Member(name, size, is_dir, item))
    return result


def _payload(reader: zipfile.ZipFile | tarfile.TarFile, member: _Member) -> BinaryIO:
    if isinstance(reader, zipfile.ZipFile):
        return cast(BinaryIO, reader.open(cast(zipfile.ZipInfo, member.original)))
    payload = reader.extractfile(cast(tarfile.TarInfo, member.original))
    if payload is None:
        raise ValueError("ARCHIVE_TYPE_INVALID: 无法读取普通数据文件")
    return cast(BinaryIO, payload)


@contextmanager
def _archive_reader(file: BinaryIO) -> Iterator[zipfile.ZipFile | tarfile.TarFile]:
    is_zip = zipfile.is_zipfile(file)
    file.seek(0)
    try:
        if is_zip:
            with zipfile.ZipFile(file) as zipped:
                yield zipped
        else:
            with tarfile.open(fileobj=file, mode="r:*") as tar:
                yield tar
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        raise ValueError("ARCHIVE_FORMAT_INVALID: 数据归档格式或成员结构损坏") from exc


def _check_payload(stream: BinaryIO, expected: OfflineFile, output: BinaryIO | None = None) -> None:
    value = hashlib.sha256()
    size = 0
    while chunk := stream.read(CHUNK_SIZE):
        size += len(chunk)
        if size > expected.size_bytes:
            raise ValueError("ARCHIVE_PAYLOAD_INVALID: 实际解压数据超过清单大小")
        value.update(chunk)
        if output is not None:
            output.write(chunk)
    if size != expected.size_bytes or value.hexdigest() != expected.sha256:
        raise ValueError("ARCHIVE_PAYLOAD_INVALID: 数据大小或 SHA-256 与可信清单不一致")


def _destination(path: Path) -> Path:
    path = path.absolute()
    if ".." in path.parts or any(item.is_symlink() for item in (*path.parents, path)):
        raise ValueError("DESTINATION_UNSAFE: 目的路径不能使用链接或父目录跳转")
    if path.exists():
        raise ValueError("DESTINATION_EXISTS: 目的路径已存在，不覆盖用户数据或重复导入")
    return path


@contextmanager
def _checked_archive(
    path: Path, expected_sha256: str, destination: Path, *, max_archive_bytes: int,
    max_total_bytes: int, max_member_bytes: int, max_members: int,
) -> Iterator[tuple[ValidatedOfflineArchive, zipfile.ZipFile | tarfile.TarFile, dict[str, _Member], BinaryIO]]:
    expected = _digest(expected_sha256)
    destination = _destination(destination)
    if any(type(limit) is not int or limit <= 0 for limit in (
        max_archive_bytes, max_total_bytes, max_member_bytes, max_members,
    )):
        raise ValueError("ARCHIVE_CAPACITY: 容量限制必须为正整数")
    path = path.absolute()
    if any(item.is_symlink() for item in (*path.parents, path)):
        raise ValueError("ARCHIVE_PATH_INVALID: 数据归档不能是符号链接")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValueError("ARCHIVE_UNAVAILABLE: 无法只读打开普通数据归档") from exc
    with os.fdopen(descriptor, "rb") as file:
        observed = os.fstat(file.fileno())
        if not stat.S_ISREG(observed.st_mode):
            raise ValueError("ARCHIVE_TYPE_INVALID: 归档必须是普通文件")
        if observed.st_size > max_archive_bytes:
            raise ValueError("ARCHIVE_CAPACITY: 归档文件超过下载/导入容量限制")
        if _hash(file) != expected:
            raise ValueError("ARCHIVE_DIGEST_MISMATCH: 归档实际 SHA-256 与可信值不符")
        with _archive_reader(file) as reader:
            members = _members(reader, max_members, max_member_bytes, max_total_bytes)
            by_name = {item.name: item for item in members}
            manifest_member = by_name.get(MANIFEST_NAME)
            if manifest_member is None or manifest_member.is_dir or manifest_member.size > MANIFEST_LIMIT:
                raise ValueError("MANIFEST_INVALID: 缺少受限大小的数据清单")
            with _payload(reader, manifest_member) as payload:
                raw = payload.read(MANIFEST_LIMIT + 1)
            if len(raw) > MANIFEST_LIMIT:
                raise ValueError("MANIFEST_INVALID: 数据清单超过容量限制")
            bundle_id, files = _manifest(raw)
            declared = {item.path for item in files}
            declared_keys = {_filename_key(name) for name in declared}
            actual = {item.name for item in members if not item.is_dir and item.name != MANIFEST_NAME}
            if declared != actual:
                raise ValueError("MANIFEST_INVALID: 归档文件与清单不一致，不接受额外文件")
            if any(item.size_bytes > max_member_bytes for item in files) or sum(item.size_bytes for item in files) > max_total_bytes:
                raise ValueError("ARCHIVE_CAPACITY: 数据解压大小超过限制")
            for member in members:
                if member.is_dir and not any(name.startswith(member.name + "/") for name in declared):
                    raise ValueError("MANIFEST_INVALID: 归档包含未声明的目录")
                if not member.is_dir and any(name.startswith(_filename_key(member.name) + "/") for name in declared_keys):
                    raise ValueError("ARCHIVE_PATH_INVALID: 同一路径不能同时是文件和父目录")
            for item in files:
                if by_name[item.path].size != item.size_bytes:
                    raise ValueError("ARCHIVE_PAYLOAD_INVALID: 成员大小与清单不符")
                with _payload(reader, by_name[item.path]) as payload:
                    _check_payload(payload, item)
            if _hash(file) != expected:
                raise ValueError("ARCHIVE_DIGEST_MISMATCH: 验证时归档内容发生变化")
            yield ValidatedOfflineArchive(path, destination, expected, bundle_id, files,
                                          sum(item.size_bytes for item in files)), reader, by_name, file


def validate_offline_archive(
    path: Path, expected_sha256: str, destination: Path, *,
    max_archive_bytes: int = 536870912, max_total_bytes: int = 536870912,
    max_member_bytes: int = 268435456, max_members: int = 1024,
) -> ValidatedOfflineArchive:
    """Read and validate a trusted data-only archive; make no filesystem changes."""
    with _checked_archive(path, expected_sha256, destination, max_archive_bytes=max_archive_bytes,
                          max_total_bytes=max_total_bytes, max_member_bytes=max_member_bytes,
                          max_members=max_members) as (result, _, _, _):
        return result


def _publish_no_replace(source: Path, destination: Path) -> None:
    # Atomic exclusive rename: a racing user directory must never be replaced.
    native = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = native.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(native, "renameat2"):
        rename = native.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)  # RENAME_NOREPLACE
    else:
        raise ValueError("DESTINATION_UNSUPPORTED: 当前平台缺少不覆盖式原子发布支持")
    if result != 0:
        raise ValueError(f"DESTINATION_UNAVAILABLE: 不覆盖式发布失败，errno={ctypes.get_errno()}")


def import_offline_archive(
    path: Path, expected_sha256: str, destination: Path, *,
    max_archive_bytes: int = 536870912, max_total_bytes: int = 536870912,
    max_member_bytes: int = 268435456, max_members: int = 1024,
) -> ValidatedOfflineArchive:
    """Import fully verified data atomically; never run scripts or overwrite files."""
    with _checked_archive(path, expected_sha256, destination, max_archive_bytes=max_archive_bytes,
                          max_total_bytes=max_total_bytes, max_member_bytes=max_member_bytes,
                          max_members=max_members) as (result, reader, members, archive_file):
        parent = ensure_private_state_dir(result.destination.parent)
        staging = Path(tempfile.mkdtemp(prefix=".d1env-import-", dir=parent))
        try:
            for item in result.files:
                target = staging / item.path
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, "wb") as output, _payload(reader, members[item.path]) as payload:
                    _check_payload(payload, item, output)
                    output.flush()
                    os.fsync(output.fileno())
            if _hash(archive_file) != result.sha256:
                raise ValueError("ARCHIVE_DIGEST_MISMATCH: 导入时归档内容发生变化")
            _publish_no_replace(staging, result.destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)  # Only this newly-created, private staging directory.
        return result
