from datetime import timedelta
from pathlib import Path

from d1env.catalog import load_catalog
from d1env.models import DeploymentRequest, HostFacts, utcnow
from d1env.planner import resolve

ROOT = Path(__file__).resolve().parents[1]


def host():
    return HostFacts(os_name="Darwin", os_version="26", architecture="aarch64",
                     docker_available=False, docker_accessible=False, compose_available=False,
                     disk_free_bytes=1024**3, gpu_available=False, checked_at=utcnow())


def test_unknown_profile_blocks_real_deploy():
    result = resolve(DeploymentRequest(mode="real_readonly", profile_id="unknown"), host(), load_catalog(ROOT / "profiles"))
    assert result.plan is None
    assert "PROFILE_UNVERIFIED" in [b.code for b in result.blockers]


def test_real_profiles_block_without_artifacts():
    for profile in ["edu-zsl-1", "edu-zsl-1w", "maxpro"]:
        result = resolve(DeploymentRequest(mode="real_readonly", profile_id=profile), host(), load_catalog(ROOT / "profiles"))
        assert result.plan is None
        assert {"ADAPTER_UNAVAILABLE", "ARTIFACT_UNAVAILABLE"} <= {b.code for b in result.blockers}


def test_mock_plan_never_requires_robot_network_or_gpu():
    result = resolve(DeploymentRequest(), host(), load_catalog(ROOT / "profiles"))
    assert result.blockers == [] and result.plan is not None
    assert result.plan.verified_scope == "mock"
    assert result.plan.network == "none"
    assert all(op.kind == "mock_step" for op in result.plan.operations)
    assert result.plan.download_bytes is None


def test_plan_id_stable_under_key_order_and_probe_timestamp():
    catalog = load_catalog(ROOT / "profiles")
    first = resolve(DeploymentRequest(), host(), catalog).plan
    later = host().model_copy(update={"checked_at": utcnow() + timedelta(days=1)})
    catalog.profiles[0].capabilities = dict(reversed(list(catalog.profiles[0].capabilities.items())))
    second = resolve(DeploymentRequest(), later, catalog).plan
    assert first is not None and second is not None
    assert first.plan_id == second.plan_id
    demo = next(p for p in catalog.profiles if p.profile_id == "demo")
    demo.profile_revision = "foundation-2"
    changed = resolve(DeploymentRequest(), later, catalog).plan
    assert changed is not None and changed.plan_id != first.plan_id


def test_hardware_never_silently_downgrades_to_mock():
    result = resolve(DeploymentRequest(profile_id="maxpro"), host(), load_catalog(ROOT / "profiles"))
    assert result.plan is None
    assert result.blockers[0].code == "MODE_PROFILE_MISMATCH"


def test_failure_injection_is_a_distinct_explicit_mock_plan():
    catalog = load_catalog(ROOT / "profiles")
    normal = resolve(DeploymentRequest(), host(), catalog).plan
    failure = resolve(DeploymentRequest(demo_scenario="verify_failure"), host(), catalog).plan
    assert normal and failure and normal.plan_id != failure.plan_id
    assert failure.operations[-1].operation_id == "verify_failure"
