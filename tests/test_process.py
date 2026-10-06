import subprocess

import pytest

from d1env.process import ProbeRunner


@pytest.mark.parametrize("argv", [
    ("sh", "-c", "echo unsafe"), ("docker", "run", "ubuntu"),
    ("docker", "info; touch /tmp/unsafe"), ("docker", "--host", "tcp://evil", "info"),
])
def test_only_known_readonly_argv_allowed(argv, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("untrusted argv reached process creation")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError):
        ProbeRunner().run(argv)


def test_missing_executable_is_structured(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("missing")
    monkeypatch.setattr(subprocess, "Popen", missing)
    result = ProbeRunner().run(("docker", "--context", "default", "info", "--format", "{{json .ServerVersion}}"))
    assert result.returncode is None
    assert not result.timed_out
    assert "missing" in result.stderr


def test_probe_timeout_is_structured(monkeypatch):
    class Process:
        pid = 999999999
        returncode = -9
        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("docker", timeout)
            return -9
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: Process())
    result = ProbeRunner().run(("docker", "--context", "default", "compose", "version", "--short"), timeout_s=.01)
    assert result.timed_out and result.returncode is None


def test_output_is_bounded_and_marked(monkeypatch):
    def large(*args, **kwargs):
        assert kwargs.get("shell") is False
        kwargs["stdout"].write(b"x" * 100000)
        class Process:
            returncode = 0
            def wait(self, timeout=None):
                return 0
        return Process()
    monkeypatch.setattr(subprocess, "Popen", large)
    result = ProbeRunner().run(("docker", "--context", "default", "info", "--format", "{{json .ServerVersion}}"))
    assert len(result.stdout.encode()) <= 32768
    assert "TRUNCATED" in result.stdout


def test_malformed_utf8_cannot_expand_output_beyond_limit(monkeypatch):
    def invalid(*args, **kwargs):
        kwargs["stdout"].write(b"\xff" * 100000)
        class Process:
            returncode = 0
            def wait(self, timeout=None):
                return 0
        return Process()
    monkeypatch.setattr(subprocess,"Popen",invalid)
    result = ProbeRunner().run(("docker", "--context", "default", "info", "--format", "{{json .ServerVersion}}"))
    assert len(result.stdout.encode()) <= 32768
    assert "TRUNCATED" in result.stdout


def test_timeout_marker_stays_within_combined_output_limit(monkeypatch):
    def full(*args, **kwargs):
        kwargs["stdout"].write(b"x" * 32768)
        kwargs["stderr"].write(b"y" * 32768)
        class Process:
            pid = 999999999
            returncode = -9
            def wait(self, timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired("docker", timeout)
                return -9
        return Process()
    monkeypatch.setattr(subprocess, "Popen", full)
    result = ProbeRunner().run(("docker", "--context", "default", "compose", "version", "--short"), timeout_s=.01)
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 65536
    assert result.timed_out and "probe timed out" in result.stderr
    assert "TRUNCATED" in result.stderr
