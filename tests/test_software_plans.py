from datetime import timedelta

import pytest
from pydantic import ValidationError

from d1env.models import ArtifactRef, Catalog, DeploymentRequest, HostFacts, Profile, utcnow
from d1env.planner import resolve


def software_catalog(artifact=True):
    return Catalog(profiles=[Profile.model_validate({
        "profile_id": "ros-probe", "name": "ROS 软件通信测试（未接真机）",
        "kind": "software", "profile_revision": "m3-test-fixture",
        "vendor": None, "sdk_family": None, "variant": "cpu_ros_probe",
        "architectures": ["aarch64"], "runtime_requirements": {"gpu_required": False, "min_disk_bytes": 1073741824},
        "capabilities": {}, "network_requirements": ["none"],
        "artifact_requirements": [{"kind": "local_build", "source": "d1env/ros-probe",
                                   "architecture": "aarch64", "immutable_id": "sha256:" + "a" * 64}] if artifact else [],
    })])


def software_host(**updates):
    fields = {"os_name": "Darwin", "os_version": "26", "architecture": "aarch64",
              "docker_available": True, "docker_accessible": True, "compose_available": True,
              "disk_free_bytes": 10 * 1024**3, "gpu_available": None, "checked_at": utcnow(),
              "docker_os": "linux", "docker_architecture": "aarch64", "docker_version": "29.6.1"}
    return HostFacts(**{**fields, **updates})


def request(**updates):
    return DeploymentRequest(**{"mode": "software_test", "profile_id": "ros-probe",
                                 "task": "ros_probe", **updates})


def test_mac_deploys_only_software_probe_using_linux_docker_evidence():
    result = resolve(request(), software_host(), software_catalog())
    assert result.blockers == [] and result.plan is not None
    plan = result.plan
    assert plan.mode == "software_test" and plan.verified_scope == "software"
    assert plan.network == "project_internal"
    assert [step.operation_id for step in plan.operations] == ["preflight", "acquire", "configure", "start", "verify"]
    assert all(step.kind == "docker_step" for step in plan.operations)
    assert plan.required_evidence == ("software_ready",)
    assert all(step.artifact.immutable_id == "sha256:" + "a" * 64 for step in plan.operations)
    assert not any("/dev" in item for item in plan.directories)


@pytest.mark.parametrize("updates,code", [
    ({"docker_accessible": False, "docker_error": "permission_denied"}, "DOCKER_UNAVAILABLE"),
    ({"compose_available": False}, "COMPOSE_UNAVAILABLE"),
    ({"docker_architecture": "x86_64"}, "ARTIFACT_ARCHITECTURE_MISMATCH"),
    ({"docker_os": None}, "DOCKER_PLATFORM_UNVERIFIED"),
    ({"disk_free_bytes": 500 * 1024**2}, "DISK_UNVERIFIED"),
])
def test_real_software_requires_actual_daemon_and_matching_artifact(updates, code):
    result = resolve(request(), software_host(**updates), software_catalog())
    assert result.plan is None
    assert code in [blocker.code for blocker in result.blockers]


def test_no_build_is_a_blocker_and_never_uses_fake_digest():
    result = resolve(request(), software_host(), software_catalog(artifact=False))
    assert result.plan is None
    assert "ARTIFACT_UNAVAILABLE" in [item.code for item in result.blockers]


def test_unknown_image_source_and_mock_artifacts_are_not_executable():
    from d1env.models import Operation
    for artifact in [ArtifactRef(kind="mock"), ArtifactRef(kind="local_build", source="arbitrary/image",
                     architecture="aarch64", immutable_id="sha256:" + "a" * 64)]:
        with pytest.raises(ValidationError):
            Operation(operation_id="acquire", kind="docker_step", label="test", artifact=artifact)


def test_plan_keeps_software_fault_injection_explicit_and_deterministic():
    catalog = software_catalog()
    first = resolve(request(), software_host(), catalog).plan
    later = resolve(request(), software_host(checked_at=utcnow() + timedelta(days=1)), catalog).plan
    failure = resolve(request(probe_scenario="no_publisher"), software_host(), catalog).plan
    assert first is not None and later is not None and failure is not None
    assert first.plan_id == later.plan_id != failure.plan_id
    assert failure.operations[-1].probe_scenario == "no_publisher"
    assert "故障注入" in failure.operations[-1].label


def test_mode_mismatch_and_arbitrary_execution_fields_are_rejected():
    result = resolve(DeploymentRequest(profile_id="ros-probe"), software_host(), software_catalog())
    assert result.plan is None and result.blockers[0].code == "MODE_PROFILE_MISMATCH"
    with pytest.raises(ValidationError):
        request(image="attacker/image", command="sh")
    with pytest.raises(ValidationError):
        DeploymentRequest(probe_scenario="no_publisher")


def test_catalog_has_separate_software_probe_without_robot_capabilities():
    from pathlib import Path

    from d1env.catalog import load_catalog
    catalog = load_catalog(Path(__file__).resolve().parents[1] / "profiles")
    assert any(profile.profile_id == "ros-probe" for profile in catalog.profiles)
    profile = next(item for item in catalog.profiles if item.profile_id == "ros-probe")
    assert profile.kind == "software" and profile.sdk_family is None
    assert profile.capabilities["robot_telemetry"].status == "not_implemented"
