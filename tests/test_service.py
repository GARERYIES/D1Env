from pathlib import Path

import pytest

from d1env.models import DeploymentRequest, HostFacts, utcnow
from d1env.service import ApplicationService

ROOT = Path(__file__).resolve().parents[1]


def facts():
    return HostFacts(os_name="Darwin",os_version="26",architecture="aarch64",docker_available=False,
                     docker_accessible=False,compose_available=False,disk_free_bytes=1024**3,
                     gpu_available=None,checked_at=utcnow())


def test_start_only_saved_current_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("d1env.service.inspect_host",lambda target,runner: facts())
    service = ApplicationService(ROOT,tmp_path)
    with pytest.raises(KeyError):
        service.start("not-server-saved", "key-1")
    plan = service.preview(DeploymentRequest()).plan
    assert plan
    next(p for p in service.catalog.profiles if p.profile_id == "demo").profile_revision = "changed"
    with pytest.raises(ValueError,match="PLAN_CHANGED"):
        service.start(plan.plan_id,"key-2")


def test_start_rechecks_disk_instead_of_trusting_old_preview(tmp_path, monkeypatch):
    current = facts()
    monkeypatch.setattr("d1env.service.inspect_host",lambda target,runner: current)
    service = ApplicationService(ROOT,tmp_path)
    plan = service.preview(DeploymentRequest()).plan
    assert plan
    current.disk_free_bytes = 1
    with pytest.raises(ValueError,match="PREFLIGHT_BLOCKED"):
        service.start(plan.plan_id,"key-1")
