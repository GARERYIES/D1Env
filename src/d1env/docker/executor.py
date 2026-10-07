"""Backend-generated Compose and business readiness for the trusted ROS probe."""

import json
import math
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

from pydantic import ValidationError

from d1env.docker.client import ID_PATTERN, INFO_FORMAT, DockerClient, DockerCommand
from d1env.models import ArtifactRef, ExecutionContext, JSONValue, Operation, OperationResult

STEPS = frozenset({"preflight", "acquire", "configure", "start", "verify"})
MANIFEST = "docker-resources.json"
COMPOSE = "compose.json"
ARCHES = {"arm64": "aarch64", "aarch64": "aarch64", "amd64": "x86_64", "x86_64": "x86_64"}


class Client(Protocol):
    def run(
        self,
        args: tuple[str, ...],
        timeout_s: float = 5.0,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> DockerCommand: ...


class DockerSafetyError(ValueError):
    code = "DOCKER_CONFIG_INVALID"


class DockerCommandError(RuntimeError):
    def __init__(self, result: DockerCommand):
        self.result = result
        self.code = (
            "DOCKER_CANCELLED"
            if result.cancelled
            else "DOCKER_TIMEOUT"
            if result.timed_out
            else "DOCKER_COMMAND_FAILED"
        )
        super().__init__(self.code)


def _json(value: str) -> JSONValue:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"invalid JSON numeric constant: {constant}")

    def unique_object(pairs: list[tuple[str, JSONValue]]) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON field is not allowed")
            result[key] = item
        return result

    return cast(
        JSONValue,
        json.loads(value, parse_constant=reject_constant, object_pairs_hook=unique_object),
    )


class DockerExecutor:
    def __init__(self, client: Client | None = None, readiness_timeout_s: float = 15.0):
        if not 0 < readiness_timeout_s <= 60:
            raise ValueError("readiness timeout must be finite and <=60 seconds")
        self.client = client or DockerClient()
        self.readiness_timeout_s = readiness_timeout_s

    @staticmethod
    def _validate_context(context: ExecutionContext) -> Path:
        if (
            context.mode != "software_test"
            or context.target_id != "local"
            or not re.fullmatch(r"[0-9a-f]{32}", context.job_id)
            or context.plan_id is None
            or not re.fullmatch(r"[0-9a-f]{64}", context.plan_id)
        ):
            raise DockerSafetyError("软件测试的作业或计划身份不完整；请重新预览。")
        directory = context.work_dir.absolute()
        if directory.resolve() != directory or directory.is_symlink() or not directory.is_dir():
            raise DockerSafetyError(
                "作业目录存在符号链接、路径逃逸或尚未建立；请检查本项目状态目录。"
            )
        for name in (MANIFEST, COMPOSE):
            path = directory / name
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise DockerSafetyError(
                    "资源记录或 Compose 路径不是普通文件；请保护用户文件并重新检查目录。"
                )
        return directory

    @staticmethod
    def _validate_artifact(artifact: ArtifactRef | None) -> ArtifactRef:
        try:
            checked = ArtifactRef.model_validate(artifact.model_dump() if artifact else {})
        except ValidationError as error:
            raise DockerSafetyError(
                "可信 ROS 工件字段或不可变标识无效；请重新选择随包配置。"
            ) from error
        if (
            checked.kind != "local_build"
            or checked.source != "d1env/ros-probe"
            or checked.architecture not in {"aarch64", "x86_64"}
        ):
            raise DockerSafetyError("本轮仅执行 d1env/ros-probe 的已锁定本地构建；不接受任意镜像。")
        return checked

    @staticmethod
    def _labels(context: ExecutionContext) -> dict[str, str]:
        return {
            "io.d1env.project": "d1env",
            "io.d1env.job": context.job_id,
            "io.d1env.plan": str(context.plan_id),
        }

    @staticmethod
    def _name(context: ExecutionContext, role: str) -> str:
        return f"d1env-{context.job_id}-{role}"

    def _compose(
        self, context: ExecutionContext, artifact: ArtifactRef, scenario: str
    ) -> dict[str, JSONValue]:
        services: dict[str, JSONValue] = {}
        for role, command in (
            ("pub", "idle" if scenario == "no_publisher" else "publisher"),
            ("sub", "subscriber"),
        ):
            services[role] = {
                "image": artifact.immutable_id,
                "pull_policy": "never",
                "container_name": self._name(context, role),
                "command": [command],
                "user": "10001:10001",
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "tmpfs": ["/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1770"],
                "cpus": 0.5,
                "mem_limit": "256m",
                "pids_limit": 128,
                "environment": {
                    "D1ENV_RUN_ID": context.job_id,
                    "ROS_DOMAIN_ID": "31",
                    "ROS_LOG_DIR": "/tmp/ros-logs",
                    "HOME": "/tmp",
                },
                "networks": ["probe"],
                "restart": "no",
                "labels": {**self._labels(context), "io.d1env.role": role},
                "logging": {
                    "driver": "local",
                    "options": {"max-size": "2m", "max-file": "1", "compress": "false"},
                },
            }
        return {
            "services": services,
            "networks": {
                "probe": {
                    "name": self._name(context, "network"),
                    "driver": "bridge",
                    "internal": True,
                    "labels": {**self._labels(context), "io.d1env.role": "network"},
                }
            },
        }

    @staticmethod
    def _read_file(path: Path) -> JSONValue:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise DockerSafetyError("项目记录超出 64 KiB 限制；请核对文件。")
        return _json(raw.decode("utf-8"))

    @staticmethod
    def _write_file(path: Path, payload: dict[str, JSONValue]) -> None:
        if path.is_symlink():
            raise DockerSafetyError("禁止通过符号链接写入项目记录。")
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        if len(raw) > 65536:
            raise DockerSafetyError("项目记录超出 64 KiB 限制。")
        temporary = path.parent / f".d1env-{uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _manifest(self, context: ExecutionContext) -> dict[str, JSONValue] | None:
        path = self._validate_context(context) / MANIFEST
        if not path.exists():
            return None
        payload = self._read_file(path)
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "job_id",
            "plan_id",
            "image_id",
            "scenario",
            "resources",
        }:
            raise DockerSafetyError("资源记录结构无效；禁止据此停止任何 Docker 对象。")
        if (
            payload["schema_version"] != 1
            or payload["job_id"] != context.job_id
            or payload["plan_id"] != context.plan_id
            or not isinstance(payload["image_id"], str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", payload["image_id"])
            or payload["scenario"] not in ("success", "no_publisher")
        ):
            raise DockerSafetyError("资源记录身份与当前作业不符；保留现有资源以便核对。")
        resources = payload["resources"]
        if not isinstance(resources, list) or len(resources) > 3:
            raise DockerSafetyError("资源记录数量或类型无效。")
        seen: set[str] = set()
        for resource in resources:
            if (
                not isinstance(resource, dict)
                or set(resource) != {"kind", "id", "role"}
                or resource["kind"] not in ("container", "network")
                or not isinstance(resource["id"], str)
                or not ID_PATTERN.fullmatch(resource["id"])
                or resource["role"] not in ("pub", "sub", "network")
                or resource["id"] in seen
            ):
                raise DockerSafetyError("资源 ID、归属角色或字段无效；保留资源。")
            if (resource["kind"] == "network") != (resource["role"] == "network"):
                raise DockerSafetyError("资源类别与角色不符。")
            seen.add(resource["id"])
        return payload

    @staticmethod
    def _result(
        step: str,
        status: Literal["succeeded", "failed", "cancelled"],
        message: str,
        evidence: dict[str, JSONValue] | None = None,
        code: str | None = None,
        resource_ids: list[str] | None = None,
    ) -> OperationResult:
        return OperationResult(
            operation_id=step,
            status=status,
            origin="docker",
            message=message,
            evidence=evidence or {},
            error_code=code,
            resource_ids=resource_ids or [],
        )

    def _command(
        self, args: tuple[str, ...], context: ExecutionContext, deadline: float
    ) -> DockerCommand:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DockerCommandError(
                DockerCommand(args, None, "", "步骤已达到软件超时期限", timed_out=True)
            )
        result = self.client.run(
            args, timeout_s=min(600.0, remaining), is_cancelled=context.is_cancelled
        )
        if result.returncode != 0 or result.timed_out or result.cancelled:
            raise DockerCommandError(result)
        return result

    def _inspect(
        self,
        kind: str,
        identity: str,
        context: ExecutionContext,
        deadline: float,
        missing_ok: bool = False,
    ) -> dict[str, JSONValue] | None:
        try:
            result = self._command((kind, "inspect", identity), context, deadline)
        except DockerCommandError as error:
            missing_message = error.result.stderr.lower()
            object_missing = "no such" in missing_message or (
                kind == "network" and f"network {identity} not found" in missing_message
            )
            if missing_ok and error.result.returncode == 1 and object_missing:
                return None
            raise
        value = _json(result.stdout)
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise DockerSafetyError("Docker inspect 返回无效结构；无法确认资源身份。")
        return value[0]

    def _image(
        self, artifact: ArtifactRef, context: ExecutionContext, deadline: float
    ) -> dict[str, JSONValue]:
        metadata = self._inspect("image", str(artifact.immutable_id), context, deadline)
        assert metadata is not None
        configuration = metadata.get("Config")
        labels = configuration.get("Labels") if isinstance(configuration, dict) else None
        if (
            metadata.get("Id") != artifact.immutable_id
            or metadata.get("Os") != "linux"
            or ARCHES.get(str(metadata.get("Architecture"))) != artifact.architecture
            or not isinstance(labels, dict)
            or labels.get("io.d1env.source") != artifact.source
        ):
            raise DockerSafetyError("实际镜像 ID、来源、Linux 运行时或 CPU 架构不符；禁止启动。")
        return metadata

    def _owned(
        self,
        metadata: dict[str, JSONValue],
        resource: dict[str, JSONValue],
        context: ExecutionContext,
        image_id: str,
    ) -> bool:
        labels_value = (
            metadata.get("Labels") if resource["kind"] == "network" else metadata.get("Config", {})
        )
        if resource["kind"] == "container":
            labels_value = labels_value.get("Labels") if isinstance(labels_value, dict) else None
        if (
            not isinstance(labels_value, dict)
            or any(labels_value.get(key) != value for key, value in self._labels(context).items())
            or labels_value.get("io.d1env.role") != resource["role"]
        ):
            return False
        if metadata.get("Id") != resource["id"] or str(metadata.get("Name", "")).lstrip(
            "/"
        ) != self._name(context, str(resource["role"])):
            return False
        if resource["kind"] == "container":
            return metadata.get("Image") == image_id
        return metadata.get("Internal") is True and metadata.get("Driver") == "bridge"

    def _discover(self, context: ExecutionContext, deadline: float) -> list[dict[str, JSONValue]]:
        found: list[dict[str, JSONValue]] = []
        filters = (
            "--filter",
            "label=io.d1env.project=d1env",
            "--filter",
            f"label=io.d1env.job={context.job_id}",
            "--filter",
            f"label=io.d1env.plan={context.plan_id}",
        )
        for kind in ("container", "network"):
            prefix = (
                ("container", "ls", "--all", "--quiet", "--no-trunc")
                if kind == "container"
                else ("network", "ls", "--quiet", "--no-trunc")
            )
            output = self._command((*prefix, *filters), context, deadline).stdout
            identities = output.splitlines()
            if len(identities) > 8:
                raise DockerSafetyError("同作业发现过多资源；禁止按名称认领或删除。")
            for identity in identities:
                if not ID_PATTERN.fullmatch(identity):
                    raise DockerSafetyError("Docker 返回的资源 ID 无效。")
                metadata = self._inspect(kind, identity, context, deadline)
                assert metadata is not None
                labels = metadata.get("Labels") if kind == "network" else metadata.get("Config", {})
                if kind == "container":
                    labels = labels.get("Labels") if isinstance(labels, dict) else None
                role = labels.get("io.d1env.role") if isinstance(labels, dict) else None
                found.append({"kind": kind, "id": identity, "role": role})
        return found

    def _configure(
        self, operation: Operation, context: ExecutionContext, image: ArtifactRef
    ) -> OperationResult:
        directory = self._validate_context(context)
        config = self._compose(context, image, operation.probe_scenario)
        path = directory / COMPOSE
        if path.exists() and self._read_file(path) != config:
            raise DockerSafetyError("现有 Compose 与固定后端配置不符；禁止覆盖或执行。")
        manifest = self._manifest(context)
        if manifest and (
            manifest["image_id"] != image.immutable_id
            or manifest["scenario"] != operation.probe_scenario
        ):
            raise DockerSafetyError("现有资源记录绑定不同工件或故障场景；禁止覆盖。")
        if not path.exists():
            self._write_file(path, config)
        if manifest is None:
            self._write_file(
                directory / MANIFEST,
                {
                    "schema_version": 1,
                    "job_id": context.job_id,
                    "plan_id": context.plan_id,
                    "image_id": image.immutable_id,
                    "scenario": operation.probe_scenario,
                    "resources": [],
                },
            )
        return self._result(
            "configure",
            "succeeded",
            "软件测试配置已生成；仅使用内部网络、非 root 用户及本项目资源。",
            {"compose_generated": True, "host_mounts": False, "public_ports": False},
        )

    def _start(
        self, operation: Operation, context: ExecutionContext, image: ArtifactRef, deadline: float
    ) -> OperationResult:
        directory = self._validate_context(context)
        manifest = self._manifest(context)
        expected = self._compose(context, image, operation.probe_scenario)
        if (
            manifest is None
            or manifest["image_id"] != image.immutable_id
            or manifest["scenario"] != operation.probe_scenario
            or not (directory / COMPOSE).exists()
            or self._read_file(directory / COMPOSE) != expected
        ):
            raise DockerSafetyError(
                "固定 Compose 或资源记录缺失/被修改；请重新预览，不执行任意配置。"
            )
        self._image(image, context, deadline)
        resources = cast(list[dict[str, JSONValue]], manifest["resources"])
        if resources:
            if len(resources) != 3:
                raise DockerSafetyError("此前创建的资源不完整；先核对盘点，再显式重试。")
            for resource in resources:
                metadata = self._inspect(
                    str(resource["kind"]), str(resource["id"]), context, deadline, missing_ok=True
                )
                if not metadata or not self._owned(
                    metadata, resource, context, str(image.immutable_id)
                ):
                    raise DockerSafetyError("登记的资源已消失或归属改变；禁止按名称重建。")
            return self._result(
                "start",
                "succeeded",
                "复用本作业已登记的软件资源；仍须独立检查业务就绪。",
                {"resources_reused": True},
                resource_ids=[str(item["id"]) for item in resources],
            )
        # Names are used only for detecting a collision, never for claiming or deletion.
        for kind, role in (("container", "pub"), ("container", "sub"), ("network", "network")):
            existing = self._inspect(
                kind, self._name(context, role), context, deadline, missing_ok=True
            )
            if existing:
                return self._result(
                    "start",
                    "failed",
                    "启动失败：同名 Docker 对象已存在但没有本次创建记录；请保留并核对外部资源。",
                    {"foreign_resource_id": existing.get("Id")},
                    "DOCKER_RESOURCE_CONFLICT",
                )
        if self._discover(context, deadline):
            return self._result(
                "start",
                "failed",
                "启动失败：发现未登记的同标签资源；请核对盘点，禁止自动认领。",
                {"untracked_resources_preserved": True},
                "DOCKER_RESOURCE_CONFLICT",
            )
        args = (
            "compose",
            "--project-name",
            f"d1env-{context.job_id}",
            "--file",
            str(directory / COMPOSE),
            "up",
            "--detach",
            "--pull",
            "never",
            "--no-build",
        )
        remaining = deadline - time.monotonic()
        result = self.client.run(
            args, timeout_s=max(0.001, min(600, remaining)), is_cancelled=context.is_cancelled
        )
        # Read-only bounded accounting after cancellation/partial creation prevents blind cleanup.
        accounting = context.model_copy(update={"is_cancelled": lambda: False})
        discovered = self._discover(accounting, time.monotonic() + 5)
        owned: list[JSONValue] = []
        for resource in discovered:
            metadata = self._inspect(
                str(resource["kind"]), str(resource["id"]), accounting, time.monotonic() + 2
            )
            if metadata and self._owned(metadata, resource, context, str(image.immutable_id)):
                owned.append(resource)
        manifest["resources"] = owned
        self._write_file(directory / MANIFEST, manifest)
        if result.returncode != 0 or result.timed_out or result.cancelled:
            raise DockerCommandError(result)
        if len(owned) != 3:
            raise DockerSafetyError("容器创建后资源盘点不完整；不宣称启动完成。")
        return self._result(
            "start",
            "succeeded",
            "本项目软件容器已创建；尚须验证真实 ROS 接收证据。",
            {"containers_started": True, "software_ready": False},
            resource_ids=[str(cast(dict[str, JSONValue], item)["id"]) for item in owned],
        )

    @staticmethod
    def _status_valid(status: dict[str, JSONValue], context: ExecutionContext, now: float) -> bool:
        samples, sequence = status.get("sample_count"), status.get("last_sequence")
        if type(samples) is not int or samples < 3 or type(sequence) is not int or sequence < 3:
            return False
        if status.get("run_id") != context.job_id or status.get("publisher_id") != context.job_id:
            return False
        sent, received = status.get("last_sent_at"), status.get("last_received_at")
        if type(sent) not in (int, float) or type(received) not in (int, float):
            return False
        sent_number, received_number = (
            float(cast(int | float, sent)),
            float(cast(int | float, received)),
        )
        return (
            math.isfinite(sent_number)
            and math.isfinite(received_number)
            and 0 <= now - sent_number <= 5
            and 0 <= now - received_number <= 5
            and sent_number <= received_number
        )

    def _verify(
        self, context: ExecutionContext, artifact: ArtifactRef, deadline: float, wait: bool = True
    ) -> OperationResult:
        manifest = self._manifest(context)
        if manifest is None or manifest["image_id"] != artifact.immutable_id:
            return self._result(
                "verify",
                "failed",
                "软件检查失败：缺少当前工件的资源记录；请核对盘点后重新部署。",
                {"software_ready": False},
                "DOCKER_RESOURCES_MISSING",
            )
        resources = cast(list[dict[str, JSONValue]], manifest["resources"])
        if len(resources) != 3:
            return self._result(
                "verify",
                "failed",
                "软件检查失败：资源清单不完整；请核对本作业资源。",
                {"software_ready": False},
                "DOCKER_RESOURCES_MISSING",
            )
        subscriber = None
        for resource in resources:
            metadata = self._inspect(
                str(resource["kind"]), str(resource["id"]), context, deadline, missing_ok=True
            )
            if metadata is None or not self._owned(
                metadata, resource, context, str(artifact.immutable_id)
            ):
                return self._result(
                    "verify",
                    "failed",
                    "软件检查失败：容器/网络缺失或归属已改变；请核对资源身份。",
                    {"software_ready": False},
                    "DOCKER_RESOURCES_MISSING",
                )
            if resource["kind"] == "container":
                state = metadata.get("State")
                if not isinstance(state, dict) or state.get("Running") is not True:
                    return self._result(
                        "verify",
                        "failed",
                        "软件检查失败：容器已经退出；请查看诊断证据后显式重试。",
                        {"software_ready": False},
                        "DOCKER_CONTAINER_EXITED",
                    )
                if resource["role"] == "sub":
                    subscriber = str(resource["id"])
        if subscriber is None:
            raise DockerSafetyError("订阅容器身份缺失。")
        evidence: dict[str, JSONValue] = {
            "software_ready": False,
            "fault_injection": manifest["scenario"] == "no_publisher",
            "freshness_threshold_s": 5,
        }
        while time.monotonic() < deadline:
            if context.is_cancelled():
                return self._result(
                    "verify",
                    "cancelled",
                    "软件检查已取消；下一步仅清理本作业资源。",
                    evidence,
                    "DOCKER_CANCELLED",
                )
            try:
                result = self._command(
                    ("exec", subscriber, "python3", "/opt/d1env/read_status.py"), context, deadline
                )
            except DockerCommandError as error:
                evidence.update(
                    {
                        "stdout": error.result.stdout,
                        "stderr": error.result.stderr,
                        "returncode": error.result.returncode,
                        "timed_out": error.result.timed_out,
                        "cancelled": error.result.cancelled,
                    }
                )
                return self._result(
                    "verify",
                    "cancelled" if error.result.cancelled else "failed",
                    "ROS 状态读取失败；检测证据包含实际退出码/超时/取消；请检查本地 Docker 后重试。",
                    evidence,
                    error.code,
                )
            try:
                status = _json(result.stdout)
            except (ValueError, UnicodeError):
                return self._result(
                    "verify",
                    "failed",
                    "ROS 状态解析失败：不是有限数值的合法 JSON；请查看容器诊断。",
                    evidence,
                    "ROS_PROBE_INVALID_STATUS",
                )
            if not isinstance(status, dict):
                return self._result(
                    "verify",
                    "failed",
                    "ROS 状态结构无效；请检查锁定探针镜像。",
                    evidence,
                    "ROS_PROBE_INVALID_STATUS",
                )
            evidence.update(
                {
                    key: status.get(key)
                    for key in (
                        "run_id",
                        "publisher_id",
                        "sample_count",
                        "last_sequence",
                        "last_sent_at",
                        "last_received_at",
                    )
                }
            )
            if self._status_valid(status, context, time.time()):
                evidence["software_ready"] = True
                evidence["containers_running"] = True
                return self._result(
                    "verify",
                    "succeeded",
                    "真实 ROS 软件通信检查通过；未连接机器人，仅验证当前软件测试范围。",
                    evidence,
                )
            if not wait:
                break
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.1, remaining))
        return self._result(
            "verify",
            "failed",
            "ROS 接收检查失败：缺少至少 3 个当前作业的新鲜样本，或消息来源/时间不符；请查看证据并显式重试。",
            evidence,
            "ROS_PROBE_NOT_READY",
        )

    def execute(self, operation: Operation, context: ExecutionContext) -> OperationResult:
        step = operation.operation_id
        try:
            self._validate_context(context)
            image = self._validate_artifact(operation.artifact)
            if (
                operation.kind != "docker_step"
                or step not in STEPS
                or operation.probe_scenario not in ("success", "no_publisher")
            ):
                raise DockerSafetyError("仅允许固定 Docker 软件测试步骤，禁止任意命令。")
            if context.is_cancelled():
                return self._result(
                    step,
                    "cancelled",
                    "软件步骤已取消；没有启动新的 Docker 操作。",
                    code="DOCKER_CANCELLED",
                )
            deadline = time.monotonic() + operation.timeout_s
            if step == "preflight":
                result = self._command(("info", "--format", INFO_FORMAT), context, deadline)
                facts = _json(result.stdout)
                if (
                    not isinstance(facts, dict)
                    or facts.get("OSType") != "linux"
                    or ARCHES.get(str(facts.get("Architecture"))) != image.architecture
                ):
                    raise DockerSafetyError(
                        "Docker daemon OS/CPU 与软件工件不符；请选择已验证的 Linux 运行时工件。"
                    )
                self._command(("compose", "version", "--short"), context, deadline)
                return self._result(
                    step,
                    "succeeded",
                    "本地 Docker/Compose 及 Linux CPU 运行时已检查；Docker 操作权仍属于高权限信任边界。",
                    {"docker_preflight": True},
                )
            if step == "acquire":
                self._image(image, context, deadline)
                return self._result(
                    step,
                    "succeeded",
                    "已核对本地可信镜像的实际 ID 和 CPU 架构；没有下载或删除用户镜像。",
                    {"artifact_verified": True, "image_id": image.immutable_id},
                )
            if step == "configure":
                return self._configure(operation, context, image)
            if step == "start":
                return self._start(operation, context, image, deadline)
            return self._verify(
                context, image, min(deadline, time.monotonic() + self.readiness_timeout_s)
            )
        except DockerCommandError as error:
            return self._result(
                step,
                "cancelled" if error.result.cancelled else "failed",
                "Docker 软件步骤失败；检测证据包含实际退出码/超时/取消；请核对诊断后显式重试。",
                {
                    "stdout": error.result.stdout,
                    "stderr": error.result.stderr,
                    "returncode": error.result.returncode,
                    "timed_out": error.result.timed_out,
                    "cancelled": error.result.cancelled,
                    "software_ready": False,
                },
                error.code,
            )
        except (DockerSafetyError, ValueError, OSError) as error:
            return self._result(
                step,
                "failed",
                "软件步骤被阻止；检测证据："
                + str(error)
                + " 下一步：核对随包工件和本项目资源记录。",
                {"software_ready": False, "exception_type": type(error).__name__},
                "DOCKER_CONFIG_INVALID",
            )

    def verify_running(self, context: ExecutionContext, artifact: ArtifactRef) -> OperationResult:
        try:
            self._validate_context(context)
            image = self._validate_artifact(artifact)
            return self._verify(context, image, time.monotonic() + 5, wait=False)
        except DockerCommandError as error:
            return self._result(
                "verify",
                "failed",
                "当前 Docker 健康检查失败；请查看实际命令证据。",
                {
                    "software_ready": False,
                    "returncode": error.result.returncode,
                    "stderr": error.result.stderr,
                    "timed_out": error.result.timed_out,
                },
                error.code,
            )
        except (DockerSafetyError, ValueError, OSError) as error:
            return self._result(
                "verify",
                "failed",
                "当前软件资源校验失败；请核对盘点：" + str(error),
                {"software_ready": False},
                "DOCKER_CONFIG_INVALID",
            )

    def inventory(self, context: ExecutionContext) -> dict[str, JSONValue]:
        base: dict[str, JSONValue] = {
            "mode": "software_test",
            "origin": "docker",
            "verified_scope": "software",
            "resources": [],
            "untracked_resources": [],
            "inventory_complete": False,
            "remaining_owned": [],
            "preserved_resources": [],
        }
        try:
            manifest = self._manifest(context)
            accounting = context.model_copy(update={"is_cancelled": lambda: False})
            deadline = time.monotonic() + 10
            discovered = self._discover(accounting, deadline)
            tracked = cast(list[dict[str, JSONValue]], manifest["resources"]) if manifest else []
            tracked_containers = {item["id"] for item in tracked if item["kind"] == "container"}
            results: list[JSONValue] = []
            for resource in tracked:
                metadata = self._inspect(
                    str(resource["kind"]),
                    str(resource["id"]),
                    accounting,
                    deadline,
                    missing_ok=True,
                )
                owned = bool(
                    metadata
                    and manifest
                    and self._owned(metadata, resource, context, str(manifest["image_id"]))
                )
                attached = metadata.get("Containers") if metadata else None
                foreign_endpoints = bool(
                    metadata
                    and resource["kind"] == "network"
                    and (
                        not isinstance(attached, dict)
                        or any(identity not in tracked_containers for identity in attached)
                    )
                )
                results.append(
                    {
                        **resource,
                        "present": metadata is not None,
                        "owned": owned,
                        "tracked": True,
                        "preserved": metadata is not None and (not owned or foreign_endpoints),
                        "preserved_reason": "foreign_or_unknown_network_endpoints"
                        if foreign_endpoints
                        else "ownership_changed"
                        if metadata is not None and not owned
                        else None,
                    }
                )
            tracked_ids = {item["id"] for item in tracked}
            untracked: list[JSONValue] = [
                {**item, "present": True, "owned": False, "tracked": False, "preserved": True}
                for item in discovered
                if item["id"] not in tracked_ids
            ]
            base["resources"] = results + untracked
            base["untracked_resources"] = untracked
            base["remaining_owned"] = [
                item
                for item in results
                if isinstance(item, dict) and item["present"] and item["owned"]
            ]
            base["preserved_resources"] = [
                item for item in results + untracked if isinstance(item, dict) and item["preserved"]
            ]
            base["inventory_complete"] = True
        except (DockerSafetyError, DockerCommandError, ValueError, OSError) as error:
            base["error_code"] = (
                error.code
                if isinstance(error, (DockerSafetyError, DockerCommandError))
                else "DOCKER_INVENTORY_FAILED"
            )
            base["evidence"] = str(error)
            base["preserved_unverified_resources"] = True
        return base

    def cleanup(self, context: ExecutionContext) -> list[str]:
        manifest = self._manifest(context)
        if manifest is None:
            return []  # Untracked resources can be inventoried, never claimed by name.
        accounting = context.model_copy(update={"is_cancelled": lambda: False})
        deadline = time.monotonic() + 20
        resources = cast(list[dict[str, JSONValue]], manifest["resources"])
        removed: list[str] = []
        for kind in ("container", "network"):
            for resource in resources:
                if resource["kind"] != kind:
                    continue
                identity = str(resource["id"])
                metadata = self._inspect(kind, identity, accounting, deadline, missing_ok=True)
                if metadata is None or not self._owned(
                    metadata, resource, context, str(manifest["image_id"])
                ):
                    continue
                if kind == "network":
                    attached = metadata.get("Containers")
                    if not isinstance(attached, dict) or attached:
                        continue  # Preserve networks with any attached object, including foreign users.
                    self._command(("network", "rm", identity), accounting, deadline)
                else:
                    state = metadata.get("State")
                    if isinstance(state, dict) and state.get("Running"):
                        self._command(
                            ("container", "stop", "--time", "3", identity), accounting, deadline
                        )
                    # Recheck identity/ownership after stop before deletion.
                    stopped = self._inspect(
                        "container", identity, accounting, deadline, missing_ok=True
                    )
                    if stopped is None or not self._owned(
                        stopped, resource, context, str(manifest["image_id"])
                    ):
                        continue
                    self._command(("container", "rm", identity), accounting, deadline)
                removed.append(identity)
        return removed
