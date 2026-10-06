import pytest

from d1env.doctor import diagnose, inspect_host
from d1env.models import DeploymentRequest, HostFacts, ProbeResult, utcnow


class Runner:
    def __init__(self, error="", code=0, timeout=False):
        self.error, self.code, self.timeout = error, code, timeout
        self.calls = []
    def run(self, argv, timeout_s=5):
        self.calls.append(argv)
        return ProbeResult(argv=argv, returncode=self.code, stdout='"27.1.0"',
                           stderr=self.error, timed_out=self.timeout, observed_at=utcnow())


@pytest.mark.parametrize("error,code,timeout,want", [
    ("missing executable: docker", None, False, "missing"),
    ("permission denied", 1, False, "permission_denied"),
    ("Cannot connect to the Docker daemon", 1, False, "daemon_stopped"),
    ("probe timed out", None, True, "timeout"),
])
def test_docker_failures_remain_distinct(error, code, timeout, want):
    facts = inspect_host("local", Runner(error, code, timeout))
    assert facts.docker_error == want
    assert facts.docker_accessible is not True


def test_remote_or_injected_target_rejected_before_probe():
    runner = Runner()
    with pytest.raises(ValueError):
        inspect_host("local; $(touch unsafe)", runner)
    assert runner.calls == []


def facts(**kwargs):
    raw = {"os_name":"Linux", "os_version":"22.04", "architecture":"x86_64",
           "docker_available":True, "docker_accessible":True, "compose_available":True,
           "disk_free_bytes":1024**3, "gpu_available":False, "checked_at":utcnow()}
    raw.update(kwargs)
    return HostFacts(**raw)


def test_cpu_diagnostics_does_not_require_gpu():
    checks = diagnose(DeploymentRequest(task="diagnostics"), facts())
    gpu = next(c for c in checks if c.code == "GPU")
    assert gpu.status == "SKIPPED"
    assert not any(c.status == "FAIL" for c in checks)


def test_unknown_disk_is_not_pass():
    checks = diagnose(DeploymentRequest(), facts(disk_free_bytes=None))
    assert next(c for c in checks if c.code == "DISK").status == "UNKNOWN"


def test_low_disk_and_missing_compose():
    checks = diagnose(DeploymentRequest(mode="real_readonly", profile_id="unknown"),
                      facts(disk_free_bytes=1, compose_available=False))
    assert next(c for c in checks if c.code == "DISK").status == "FAIL"
    assert next(c for c in checks if c.code == "COMPOSE").status == "FAIL"


def test_macos_facts_are_not_linux_runtime():
    checks = diagnose(DeploymentRequest(mode="real_readonly", profile_id="unknown"), facts(os_name="Darwin"))
    assert next(c for c in checks if c.code == "PLATFORM").status == "FAIL"
    assert next(c for c in checks if c.code == "ROBOT").status == "UNKNOWN"
