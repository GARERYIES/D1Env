import os
import signal
import subprocess
import tempfile

from .models import ProbeResult, utcnow

PROBES = frozenset({
    ("docker", "--context", "default", "info", "--format", "{{json .ServerVersion}}"),
    ("docker", "--context", "default", "compose", "version", "--short"),
})
OUTPUT_LIMIT = 32768


def bounded_read(stream: object, suffix: str = "") -> str:
    # TemporaryFile is used so subprocess output cannot grow Python memory without bound.
    from typing import BinaryIO, cast
    file = cast(BinaryIO, stream)
    file.seek(0)
    raw = file.read(OUTPUT_LIMIT + 1)
    decoded = raw.decode("utf-8", errors="replace").encode("utf-8")
    budget = OUTPUT_LIMIT - len(suffix.encode("utf-8"))
    if len(raw) > budget or len(decoded) > budget:
        return decoded[:budget - 24].decode("utf-8", errors="ignore") + "\n[TRUNCATED]" + suffix
    return decoded.decode("utf-8") + suffix


class ProbeRunner:
    def run(self, argv: tuple[str, ...], timeout_s: float = 5.0) -> ProbeResult:
        if argv not in PROBES or not 0 < timeout_s <= 5:
            raise ValueError("only known local read-only probes with timeout <=5s")
        env = {key: value for key, value in os.environ.items()
               if key not in {"DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                process = subprocess.Popen(
                    argv, stdout=stdout, stderr=stderr, shell=False,
                    env=env, start_new_session=True,
                )
            except (OSError, ValueError) as exc:
                return ProbeResult(argv=argv, returncode=None, stdout="",
                                   stderr=f"missing executable: {type(exc).__name__}",
                                   timed_out=False, observed_at=utcnow())
            timed_out = False
            try:
                process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            return ProbeResult(
                argv=argv, returncode=None if timed_out else process.returncode,
                stdout=bounded_read(stdout),
                stderr=bounded_read(stderr, "\nprobe timed out" if timed_out else ""),
                timed_out=timed_out, observed_at=utcnow(),
            )
