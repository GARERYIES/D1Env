from d1env.doctor import diagnose, inspect_host
from d1env.models import DeploymentRequest, ProbeResult, utcnow


class MetadataProbe:
    def run(self, argv):
        stdout = '{"version":"29.6.1","os":"linux","architecture":"aarch64"}' if "info" in argv else "2.40.0"
        return ProbeResult(argv=argv, returncode=0, stdout=stdout, stderr="", timed_out=False, observed_at=utcnow())


def test_docker_execution_platform_is_observed_independently_from_mac_host():
    facts = inspect_host("local", MetadataProbe())
    assert facts.docker_os == "linux"
    assert facts.docker_architecture == "aarch64"
    assert facts.docker_version == "29.6.1"
    checks = diagnose(DeploymentRequest(mode="software_test", task="ros_probe", profile_id="ros-probe"), facts)
    platform = next(check for check in checks if check.code == "PLATFORM")
    assert platform.status == "PASS"
    assert "软件" in platform.reason and "真机" in platform.reason
    assert next(check for check in checks if check.code == "ROBOT").status == "UNKNOWN"
