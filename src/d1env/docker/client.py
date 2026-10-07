"""Fixed local Docker CLI boundary with finite output, timeout and cancellation."""

import os
import re
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .endpoint import resolve_endpoint

ID_PATTERN = re.compile(r"[0-9a-f]{64}")
NAME_PATTERN = re.compile(r"d1env-[0-9a-f]{32}-(?:pub|sub|network)")
PROJECT_PATTERN = re.compile(r"d1env-[0-9a-f]{32}")
OUTPUT_LIMIT = 65536
INFO_FORMAT = '{"OSType":{{json .OSType}},"Architecture":{{json .Architecture}},"ServerVersion":{{json .ServerVersion}}}'


@dataclass(frozen=True)
class DockerCommand:
    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False


class DockerClient:
    @staticmethod
    def _validate(args: tuple[str, ...]) -> None:
        allowed = args in {
            ("info", "--format", INFO_FORMAT),
            ("compose", "version", "--short"),
        }
        if len(args) == 3 and args[:2] == ("image", "inspect"):
            allowed = bool(re.fullmatch(r"sha256:[0-9a-f]{64}", args[2]))
        if len(args) == 3 and args[:2] in {("container", "inspect"), ("network", "inspect")}:
            allowed = bool(ID_PATTERN.fullmatch(args[2]) or NAME_PATTERN.fullmatch(args[2]))
        if len(args) == 3 and args[:2] in {("container", "rm"), ("network", "rm")}:
            allowed = bool(ID_PATTERN.fullmatch(args[2]))
        if len(args) == 5 and args[:4] == ("container", "stop", "--time", "3"):
            allowed = bool(ID_PATTERN.fullmatch(args[4]))
        # Docker exec has four arguments, with no optional shell or reader parameters.
        if (
            len(args) == 4
            and args[0] == "exec"
            and args[2:] == ("python3", "/opt/d1env/read_status.py")
        ):
            allowed = bool(ID_PATTERN.fullmatch(args[1]))
        if args[:2] in {("container", "ls"), ("network", "ls")}:
            prefix = (
                ("container", "ls", "--all", "--quiet", "--no-trunc")
                if args[0] == "container"
                else ("network", "ls", "--quiet", "--no-trunc")
            )
            filters = args[len(prefix) :]
            allowed = (
                args[: len(prefix)] == prefix
                and len(filters) == 6
                and filters[::2] == ("--filter",) * 3
            )
            if allowed:
                allowed = (
                    filters[1] == "label=io.d1env.project=d1env"
                    and bool(re.fullmatch(r"label=io\.d1env\.job=[0-9a-f]{32}", filters[3]))
                    and bool(re.fullmatch(r"label=io\.d1env\.plan=[0-9a-f]{64}", filters[5]))
                )
        if len(args) == 10 and args[:2] == ("compose", "--project-name"):
            path = Path(args[4])
            allowed = (
                bool(PROJECT_PATTERN.fullmatch(args[2]))
                and args[3] == "--file"
                and args[5:] == ("up", "--detach", "--pull", "never", "--no-build")
            )
            allowed = (
                allowed
                and path.name == "compose.json"
                and path.is_absolute()
                and not path.is_symlink()
                and path.resolve() == path.absolute()
                and path.is_file()
            )
        if len(args) == 3 and args[:2] == ("load", "--input"):
            path = Path(args[2])
            stage = path.parent.parent.parent
            allowed = (
                path.is_absolute()
                and path.name == "image.tar"
                and path.parent.name == "payload"
                and path.parent.parent.name == "unpacked"
                and bool(re.fullmatch(r"\.d1env-image-import-[a-z0-9_]+", stage.name))
                and path.is_file()
                and not path.is_symlink()
                and path.resolve() == path.absolute()
            )
            if allowed:
                observed, directory = path.stat(), stage.stat()
                allowed = (
                    observed.st_uid == os.getuid()
                    and directory.st_uid == os.getuid()
                    and not observed.st_mode & 0o077
                    and not directory.st_mode & 0o077
                )
        if not allowed:
            raise ValueError("only fixed local Docker software-test argv are accepted")

    @staticmethod
    def _read(stream: BinaryIO, budget: int) -> str:
        stream.seek(0)
        raw = stream.read(budget + 1)
        decoded = raw.decode("utf-8", errors="replace").encode("utf-8")
        if len(raw) > budget or len(decoded) > budget:
            marker = b"\n[TRUNCATED]"
            return (
                decoded[: max(0, budget - len(marker))].decode("utf-8", errors="ignore")
                + marker.decode()
            )
        return decoded.decode("utf-8")

    def run(
        self,
        args: tuple[str, ...],
        timeout_s: float = 5.0,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> DockerCommand:
        self._validate(args)
        if not 0 < timeout_s <= 600:
            raise ValueError("Docker command timeout must be finite and <=600 seconds")
        try:
            endpoint = resolve_endpoint()
        except ValueError as exc:
            return DockerCommand(("docker", "--context", "default", *args), 1, "", str(exc))
        argv = (*endpoint.prefix, *args)
        if is_cancelled():
            return DockerCommand(argv, None, "", "", cancelled=True)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("DOCKER_", "COMPOSE_"))
        }
        if endpoint.plugin_dir is not None:
            env["DOCKER_CLI_PLUGIN_EXTRA_DIRS"] = str(endpoint.plugin_dir)
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                process = subprocess.Popen(
                    argv, stdout=stdout, stderr=stderr, env=env, shell=False, start_new_session=True
                )
            except OSError as error:
                return DockerCommand(
                    argv, None, "", f"Docker executable unavailable: {type(error).__name__}"
                )
            deadline = time.monotonic() + timeout_s
            cancelled = timed_out = False
            while process.poll() is None:
                if is_cancelled():
                    cancelled = True
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=min(0.05, remaining))
                except subprocess.TimeoutExpired:
                    continue
            if cancelled or timed_out:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            out = self._read(stdout, OUTPUT_LIMIT // 2)
            err = self._read(stderr, OUTPUT_LIMIT - len(out.encode("utf-8")))
            return DockerCommand(
                argv,
                None if cancelled or timed_out else process.returncode,
                out,
                err,
                timed_out=timed_out,
                cancelled=cancelled,
            )
