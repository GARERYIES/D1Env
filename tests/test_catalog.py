from pathlib import Path

import pytest
from pydantic import ValidationError

from d1env.catalog import load_catalog, validate_profile
from d1env.models import Telemetry

ROOT = Path(__file__).resolve().parents[1]


def test_rejects_unknown_fields_and_yaml_objects(tmp_path):
    catalog = load_catalog(ROOT / "profiles")
    raw = catalog.profiles[0].model_dump()
    raw["shell"] = "touch /tmp/injected"
    with pytest.raises(ValidationError):
        validate_profile(raw)
    (tmp_path / "attack.yaml").write_text("!!python/object/apply:os.system ['echo unsafe']")
    with pytest.raises(ValueError):
        load_catalog(tmp_path)


def test_missing_telemetry_stays_unknown():
    telemetry = Telemetry()
    assert telemetry.status == "UNKNOWN"
    assert telemetry.battery_percent is None
    assert telemetry.pose is None


def test_catalog_never_promotes_hardware_capabilities():
    catalog = load_catalog(ROOT / "profiles")
    assert {"demo", "edu-zsl-1", "edu-zsl-1w", "maxpro", "unknown"} <= {
        profile.profile_id for profile in catalog.profiles}
    mock = next(p for p in catalog.profiles if p.profile_id == "demo")
    assert mock.kind == "mock" and mock.sdk_family is None
    for profile in catalog.profiles:
        if profile.kind == "hardware":
            assert all(c.status in {"documented", "not_implemented"} for c in profile.capabilities.values())
            assert profile.artifact_requirements == []
            assert profile.firmware_rules is None
    unknown = next(p for p in catalog.profiles if p.profile_id == "unknown")
    assert unknown.sdk_family is None


def test_duplicate_profiles_rejected(tmp_path):
    raw = (ROOT / "profiles/demo.yaml").read_text()
    (tmp_path / "one.yaml").write_text(raw)
    (tmp_path / "two.yaml").write_text(raw)
    with pytest.raises(ValueError, match="duplicate"):
        load_catalog(tmp_path)


def test_schema_version_and_strict_values():
    raw = load_catalog(ROOT / "profiles").profiles[0].model_dump()
    raw["schema_version"] = 2
    with pytest.raises(ValidationError):
        validate_profile(raw)
    raw["schema_version"] = 1
    raw["kind"] = "real"
    with pytest.raises(ValidationError):
        validate_profile(raw)


def test_boolean_strings_cannot_change_profile_permissions():
    raw = load_catalog(ROOT / "profiles").profiles[0].model_dump()
    raw["runtime_requirements"]["gpu_required"] = "false"
    with pytest.raises(ValidationError):
        validate_profile(raw)


def test_unobserved_or_stale_telemetry_cannot_claim_pass():
    from datetime import timedelta

    from d1env.models import utcnow
    with pytest.raises(ValidationError):
        Telemetry(status="PASS",battery_percent=82)
    with pytest.raises(ValidationError):
        Telemetry(status="PASS",battery_percent=82,pose=[0,0,0],observed_at=utcnow()-timedelta(hours=1),origin="sdk")


def test_null_or_nonfinite_samples_cannot_be_normal_telemetry():
    from d1env.models import utcnow
    with pytest.raises(ValidationError):
        Telemetry(status="PASS",observed_at=utcnow(),origin="sdk")
    with pytest.raises(ValidationError):
        Telemetry(status="PASS",battery_percent=float("nan"),pose=[0,0,0],observed_at=utcnow(),origin="sdk")
    with pytest.raises(ValidationError):
        Telemetry(status="PASS",battery_percent=80,pose=[float("inf")],observed_at=utcnow(),origin="sdk")
