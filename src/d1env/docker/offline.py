"""Import a trusted release ROS image bundle; never execute archive scripts."""

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, cast

from d1env.artifacts import import_offline_archive, validate_offline_archive
from d1env.docker.client import DockerClient
from d1env.docker.executor import ARCHES, Client, DockerCommandError, DockerExecutor, _json
from d1env.models import ArtifactRef, JSONValue
from d1env.runtime import ensure_private_state_dir

INDEX = "application/vnd.oci.image.index.v1+json"
IMAGE = "application/vnd.oci.image.manifest.v1+json"
CHUNK = 65536


def _hash(stream: BinaryIO) -> str:
    checksum = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        checksum.update(chunk)
    return checksum.hexdigest()


class OfflineImportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class ROSImageImporter:
    def __init__(
        self,
        expected_artifact: ArtifactRef,
        trusted_bundle_sha256: str,
        state_dir: Path,
        client: Client | None = None,
        *,
        max_archive_bytes: int = 1073741824,
        max_unpacked_bytes: int = 1073741824,
    ):
        self.artifact = DockerExecutor._validate_artifact(expected_artifact)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", trusted_bundle_sha256)
            or trusted_bundle_sha256 == "0" * 64
        ):
            raise ValueError("IMPORT_TRUST_REQUIRED: 外层校验值必须来自可信发行元数据")
        if any(
            type(limit) is not int or limit <= 0
            for limit in (max_archive_bytes, max_unpacked_bytes)
        ):
            raise ValueError("IMPORT_CAPACITY: 导入容量必须为正整数")
        self.trusted_sha256 = trusted_bundle_sha256
        self.state_dir = ensure_private_state_dir(state_dir)
        self.client = client or DockerClient()
        self.max_archive_bytes = max_archive_bytes
        self.max_unpacked_bytes = max_unpacked_bytes

    def _copy_private(self, source: Path, target: Path, is_cancelled: Callable[[], bool]) -> None:
        source = source.absolute()
        if source.resolve() != source or source.is_symlink():
            raise ValueError("IMPORT_PATH_INVALID: 镜像包不能是符号链接或路径跳转")
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        checksum, copied = hashlib.sha256(), 0
        with os.fdopen(descriptor, "rb") as incoming:
            observed = os.fstat(incoming.fileno())
            if not stat.S_ISREG(observed.st_mode) or observed.st_size > self.max_archive_bytes:
                raise ValueError("IMPORT_CAPACITY: 必须是容量限制内的普通镜像包")
            if shutil.disk_usage(self.state_dir).free < observed.st_size * 2 + 67108864:
                raise ValueError("IMPORT_DISK_LOW: 私有暂存磁盘不足，请保留空间后重试")
            output_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(output_fd, "wb") as output:
                while chunk := incoming.read(CHUNK):
                    if is_cancelled():
                        raise ValueError("IMPORT_CANCELLED: 镜像导入已取消，尚未调用 Docker load")
                    copied += len(chunk)
                    if copied > self.max_archive_bytes:
                        raise ValueError("IMPORT_CAPACITY: 读取时镜像包超过容量限制")
                    checksum.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        if checksum.hexdigest() != self.trusted_sha256:
            raise ValueError("IMPORT_DIGEST_MISMATCH: 私有副本 SHA-256 与可信发行值不符")

    def _ros_manifest(self, path: Path) -> dict[str, JSONValue]:
        raw = path.read_bytes()
        if len(raw) > CHUNK:
            raise ValueError("IMPORT_MANIFEST_INVALID: ROS 镜像清单过大")
        value = _json(raw.decode("utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "kind",
            "source",
            "architecture",
            "image_id",
            "image_archive",
        }:
            raise ValueError("IMPORT_MANIFEST_INVALID: ROS 镜像清单字段无效")
        if (
            type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["kind"] != "d1env_ros_image"
            or value["source"] != self.artifact.source
            or value["architecture"] != self.artifact.architecture
            or value["image_id"] != self.artifact.immutable_id
        ):
            raise ValueError("IMPORT_ARTIFACT_MISMATCH: 镜像包与当前发行 Profile 的准确身份不符")
        image = value["image_archive"]
        if (
            not isinstance(image, dict)
            or set(image) != {"path", "sha256", "size_bytes"}
            or image["path"] != "payload/image.tar"
            or not isinstance(image["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", image["sha256"])
            or type(image["size_bytes"]) is not int
            or not 0 < image["size_bytes"] <= self.max_unpacked_bytes
        ):
            raise ValueError("IMPORT_MANIFEST_INVALID: 镜像归档大小、SHA 或固定路径无效")
        return value

    def _validate_image_tar(self, path: Path, manifest: dict[str, JSONValue]) -> None:
        image_archive = cast(dict[str, JSONValue], manifest["image_archive"])
        if path.stat().st_size != image_archive["size_bytes"]:
            raise ValueError("IMPORT_IMAGE_SIZE: 镜像归档大小不符")
        with path.open("rb") as stream:
            if _hash(stream) != image_archive["sha256"]:
                raise ValueError("IMPORT_IMAGE_DIGEST: 镜像归档内容不符")
        # The save envelope has only ordinary files/directories. Rootfs layer blobs remain
        # opaque image data: legitimate filesystem links inside trusted layers are not
        # extracted to the host or treated as executable installation scripts.
        with tarfile.open(path, "r:*") as archive:
            members: dict[str, tarfile.TarInfo] = {}
            total = 0
            for member in archive:
                name = member.name.rstrip("/")
                if (
                    len(members) >= 256
                    or name in members
                    or member.sparse is not None
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError(
                        "IMPORT_IMAGE_TYPE: Docker save 含重复、链接、特殊文件或过多成员"
                    )
                if member.isdir():
                    if name not in {"blobs", "blobs/sha256"} or member.size != 0:
                        raise ValueError("IMPORT_IMAGE_PATH: 只允许固定 OCI blob 目录")
                elif name not in {"index.json", "manifest.json", "oci-layout"} and not re.fullmatch(
                    r"blobs/sha256/[0-9a-f]{64}", name
                ):
                    raise ValueError("IMPORT_IMAGE_PATH: Docker save 含未知路径或路径逃逸")
                total += member.size
                if member.size < 0 or total > self.max_unpacked_bytes:
                    raise ValueError("IMPORT_CAPACITY: Docker save 解包容量超限")
                members[name] = member

            def read(name: str, limit: int = CHUNK) -> bytes:
                member = members.get(name)
                if member is None or not member.isfile() or member.size > limit:
                    raise ValueError("IMPORT_IMAGE_MANIFEST: 固定 OCI 记录缺失或过大")
                file = archive.extractfile(member)
                if file is None:
                    raise ValueError("IMPORT_IMAGE_MANIFEST: 无法读取 OCI 记录")
                with file:
                    return file.read(limit + 1)

            for name, member in members.items():
                if member.isfile() and name.startswith("blobs/"):
                    file = archive.extractfile(member)
                    assert file is not None
                    with file:
                        if _hash(cast(BinaryIO, file)) != name.rsplit("/", 1)[1]:
                            raise ValueError("IMPORT_IMAGE_BLOB_DIGEST: OCI blob 与内容摘要不符")
            layout = _json(read("oci-layout").decode())
            top = _json(read("index.json").decode())
            if (
                layout != {"imageLayoutVersion": "1.0.0"}
                or not isinstance(top, dict)
                or top.get("schemaVersion") != 2
                or top.get("mediaType") != INDEX
                or set(top) != {"schemaVersion", "mediaType", "manifests"}
            ):
                raise ValueError("IMPORT_IMAGE_MANIFEST: 仅支持本发行的严格 OCI Docker save 包")
            roots = top["manifests"]
            if (
                not isinstance(roots, list)
                or len(roots) != 1
                or not isinstance(roots[0], dict)
                or roots[0].get("digest") != self.artifact.immutable_id
            ):
                raise ValueError("IMPORT_IMAGE_ID: OCI 根摘要与发行镜像 ID 不符")
            visited: set[str] = set()
            selected: list[dict[str, JSONValue]] = []

            def walk(descriptor: dict[str, JSONValue], depth: int = 0) -> None:
                identity, size = descriptor.get("digest"), descriptor.get("size")
                if (
                    depth > 8
                    or not isinstance(identity, str)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity)
                    or type(size) is not int
                    or size < 0
                    or "urls" in descriptor
                ):
                    raise ValueError("IMPORT_IMAGE_GRAPH: 无效 OCI descriptor 或远程引用")
                annotations = descriptor.get("annotations", {})
                if (
                    not isinstance(annotations, dict)
                    or "org.opencontainers.image.ref.name" in annotations
                ):
                    raise ValueError("IMPORT_IMAGE_TAG: 禁止离线包重新绑定用户镜像 tag")
                name = "blobs/sha256/" + identity[7:]
                member = members.get(name)
                if member is None or member.size != size:
                    raise ValueError("IMPORT_IMAGE_GRAPH: 引用 blob 缺失或大小不符")
                if name in visited:
                    return
                visited.add(name)
                media = descriptor.get("mediaType")
                if media not in {INDEX, IMAGE}:
                    return
                document = _json(read(name).decode())
                if (
                    not isinstance(document, dict)
                    or document.get("schemaVersion") != 2
                    or document.get("mediaType") != media
                ):
                    raise ValueError("IMPORT_IMAGE_GRAPH: OCI graph 结构不符")
                if media == INDEX:
                    children = document.get("manifests")
                    if not isinstance(children, list) or not 1 <= len(children) <= 8:
                        raise ValueError("IMPORT_IMAGE_GRAPH: OCI index 图无效")
                    for child in children:
                        if not isinstance(child, dict):
                            raise TypeError("IMPORT_IMAGE_GRAPH: descriptor 不是对象")
                        walk(child, depth + 1)
                else:
                    configuration, layers = document.get("config"), document.get("layers")
                    if (
                        not isinstance(configuration, dict)
                        or not isinstance(layers, list)
                        or len(layers) > 64
                    ):
                        raise ValueError("IMPORT_IMAGE_GRAPH: 镜像清单无效")
                    walk(configuration, depth + 1)
                    for layer in layers:
                        if not isinstance(layer, dict):
                            raise TypeError("IMPORT_IMAGE_GRAPH: layer descriptor 无效")
                        walk(layer, depth + 1)
                    config_name = "blobs/sha256/" + str(configuration["digest"])[7:]
                    config = _json(read(config_name).decode())
                    if isinstance(config, dict) and config.get("os") == "linux":
                        details = config.get("config")
                        labels = details.get("Labels") if isinstance(details, dict) else None
                        if (
                            ARCHES.get(str(config.get("architecture")))
                            != self.artifact.architecture
                            or not isinstance(labels, dict)
                            or labels.get("io.d1env.source") != self.artifact.source
                        ):
                            raise ValueError("IMPORT_IMAGE_CONFIG: OCI 镜像架构或来源不符")
                        selected.append(
                            {
                                "Config": config_name,
                                "Layers": [
                                    "blobs/sha256/" + str(layer["digest"])[7:]
                                    for layer in cast(list[dict[str, JSONValue]], layers)
                                ],
                            }
                        )

            walk(roots[0])
            if (
                len(selected) != 1
                or {name for name in members if name.startswith("blobs/sha256/")} != visited
            ):
                raise ValueError("IMPORT_IMAGE_GRAPH: 必须只有一个准确 Linux 镜像且没有未引用 blob")
            legacy = _json(read("manifest.json").decode())
            if (
                not isinstance(legacy, list)
                or len(legacy) != 1
                or not isinstance(legacy[0], dict)
                or set(legacy[0]) != {"Config", "RepoTags", "Layers"}
                or legacy[0]["RepoTags"] not in (None, [])
                or {"Config": legacy[0]["Config"], "Layers": legacy[0]["Layers"]} != selected[0]
            ):
                raise ValueError("IMPORT_IMAGE_TAG: Docker save 清单不符或含会覆盖用户 tag 的条目")

    def _inspect(self, is_cancelled: Callable[[], bool]) -> dict[str, JSONValue] | None:
        result = self.client.run(
            ("image", "inspect", str(self.artifact.immutable_id)),
            timeout_s=5,
            is_cancelled=is_cancelled,
        )
        if result.returncode == 1 and "no such image" in result.stderr.lower():
            return None
        if result.returncode != 0 or result.cancelled or result.timed_out:
            raise DockerCommandError(result)
        value = _json(result.stdout)
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError("IMPORT_INSPECT_INVALID: 实际镜像 inspect 结构无效")
        actual = value[0]
        config = actual.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            actual.get("Id") != self.artifact.immutable_id
            or actual.get("Os") != "linux"
            or ARCHES.get(str(actual.get("Architecture"))) != self.artifact.architecture
            or not isinstance(labels, dict)
            or labels.get("io.d1env.source") != self.artifact.source
        ):
            raise ValueError(
                "IMPORT_INSPECT_MISMATCH: 导入后实际镜像身份/架构/来源不符；保留镜像并报告失败"
            )
        return actual

    def import_bundle(
        self, path: Path, is_cancelled: Callable[[], bool] = lambda: False
    ) -> dict[str, JSONValue]:
        try:
            return self._import_bundle(path, is_cancelled)
        except DockerCommandError as error:
            result = error.result
            raise OfflineImportError(
                error.code,
                "离线 Docker 镜像导入失败；证据：退出码="
                + str(result.returncode)
                + "，超时="
                + str(result.timed_out)
                + "，取消="
                + str(result.cancelled)
                + "；"
                + result.stderr
                + " 下一步：检查本地 Docker 权限和镜像状态后重试；未删除任何用户镜像。",
            ) from error
        except (ValueError, TypeError, OSError, tarfile.TarError, UnicodeError) as error:
            code = (
                str(error).partition(":")[0]
                if isinstance(error, ValueError)
                else "IMPORT_IO_FAILED"
            )
            raise OfflineImportError(
                code,
                "离线镜像校验/导入被阻止；证据："
                + str(error)
                + " 下一步：核对可信发行包、容量和本项目状态目录后重试。",
            ) from error

    def _import_bundle(self, path: Path, is_cancelled: Callable[[], bool]) -> dict[str, JSONValue]:
        locks = ensure_private_state_dir(self.state_dir / "locks")
        descriptor = os.open(locks / "local.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        staging: Path | None = None
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(
                    "IMPORT_TARGET_BUSY: 同一电脑有活动作业或镜像导入；等待完成后重试"
                ) from error
            if is_cancelled():
                raise ValueError("IMPORT_CANCELLED: 镜像导入已取消，未运行 Docker load")
            staging = Path(tempfile.mkdtemp(prefix=".d1env-image-import-", dir=self.state_dir))
            snapshot = staging / "release-bundle.tar"
            self._copy_private(path, snapshot, is_cancelled)
            unpacked = staging / "unpacked"
            limits = {
                "max_archive_bytes": self.max_archive_bytes,
                "max_total_bytes": self.max_unpacked_bytes,
                "max_member_bytes": self.max_unpacked_bytes,
                "max_members": 8,
            }
            checked = validate_offline_archive(snapshot, self.trusted_sha256, unpacked, **limits)
            if {item.path for item in checked.files} != {
                "payload/ros-image.json",
                "payload/image.tar",
            }:
                raise ValueError("IMPORT_MANIFEST_INVALID: 离线 ROS 包只接受固定清单和 image.tar")
            if shutil.disk_usage(self.state_dir).free < checked.total_bytes + 67108864:
                raise ValueError("IMPORT_DISK_LOW: 镜像暂存空间不足")
            import_offline_archive(snapshot, self.trusted_sha256, unpacked, **limits)
            manifest = self._ros_manifest(unpacked / "payload" / "ros-image.json")
            image_path = unpacked / "payload" / "image.tar"
            self._validate_image_tar(image_path, manifest)
            if is_cancelled():
                raise ValueError("IMPORT_CANCELLED: 镜像包已验证，但导入被取消")
            receipts = ensure_private_state_dir(self.state_dir / "offline-imports")
            receipt = receipts / (self.trusted_sha256 + ".json")
            expected_receipt = {
                "schema_version": 1,
                "sha256": self.trusted_sha256,
                "image_id": self.artifact.immutable_id,
            }
            if receipt.is_symlink():
                raise ValueError("IMPORT_RECEIPT_INVALID: 导入记录不可使用符号链接")
            if receipt.exists() and (
                not receipt.is_file() or _json(receipt.read_text()) != expected_receipt
            ):
                raise ValueError(
                    "IMPORT_RECEIPT_INVALID: 现有记录不属于本次可信导入；保留文件，不覆盖"
                )
            existing = self._inspect(is_cancelled)
            if existing and receipt.is_file():
                return {
                    "status": "reused",
                    "software_scope_only": True,
                    "image_id": self.artifact.immutable_id,
                    "architecture": self.artifact.architecture,
                    "source": self.artifact.source,
                    "bundle_sha256": self.trusted_sha256,
                    "load_exit_code": None,
                }
            result = self.client.run(
                ("load", "--input", str(image_path)), timeout_s=600, is_cancelled=is_cancelled
            )
            if result.returncode != 0 or result.cancelled or result.timed_out:
                raise DockerCommandError(
                    result
                )  # Never delete images after uncertain/partial load.
            if self._inspect(lambda: False) is None:
                raise ValueError("IMPORT_IMAGE_MISSING: Docker load 后未找到发行镜像")
            if not receipt.exists():
                output_fd = os.open(
                    receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                with os.fdopen(output_fd, "w") as output:
                    json.dump(expected_receipt, output)
            return {
                "status": "imported",
                "software_scope_only": True,
                "image_id": self.artifact.immutable_id,
                "architecture": self.artifact.architecture,
                "source": self.artifact.source,
                "bundle_sha256": self.trusted_sha256,
                "load_exit_code": result.returncode,
            }
        finally:
            if staging is not None:
                shutil.rmtree(
                    staging
                )  # Only the freshly created private directory owned by this call.
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
