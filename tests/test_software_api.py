from test_software_jobs import SoftwareProcessFixture, wait_done
from test_software_plans import request, software_catalog, software_host

from d1env.models import JobSnapshot, utcnow
from d1env.reports import build_report, markdown_report


def test_software_api_plan_deploy_stop_and_auth_boundary(authenticated, service, monkeypatch):
    client, headers = authenticated
    service.catalog = software_catalog()
    service.engine._software_executor = SoftwareProcessFixture()
    monkeypatch.setattr("d1env.service.inspect_host", lambda *args: software_host())
    preview = client.post("/api/plans", json=request().model_dump(mode="json"), headers=headers)
    assert preview.status_code == 200 and preview.json()["plan"]["verified_scope"] == "software"
    plan_id = preview.json()["plan"]["plan_id"]
    started = client.post("/api/jobs", json={"plan_id": plan_id, "idempotency_key": "software-once"}, headers=headers)
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    assert wait_done(service.engine, job_id).state == "SUCCEEDED"
    saved_plan = client.get(f"/api/jobs/{job_id}/plan")
    assert saved_plan.status_code == 200 and saved_plan.json()["request"]["mode"] == "software_test"
    assert client.post(f"/api/jobs/{job_id}/stop", json={}).status_code == 403
    assert client.post(f"/api/jobs/{job_id}/stop", json={}, headers={**headers, "Origin": "https://foreign.invalid"}).status_code == 403
    stopped = client.post(f"/api/jobs/{job_id}/stop", json={}, headers=headers)
    assert stopped.status_code == 200 and stopped.json()["state"] == "CANCELLED"
    report = client.post("/api/reports", json={"job_id": job_id}, headers=headers)
    assert report.status_code == 200 and report.json()["report"]["verified_scope"] == "software"
    assert "真实软件测试" in report.json()["markdown"]


def test_report_software_scope_is_never_relabelled_mock_or_hardware_verified():
    job = JobSnapshot(job_id="a"*32, plan_id="b"*64, target_id="local", mode="software_test",
                      state="SUCCEEDED", verified_scope="software", created_at=utcnow(), updated_at=utcnow())
    report = build_report(job, [], [], source_locks={})
    content = markdown_report(report)
    assert "真实软件测试" in content and "未连接真机" in content
    assert "# D1Env 诊断报告 · MOCK" not in content
    assert "Ubuntu" in " ".join(report.unverified_items)


def test_installed_report_includes_actual_ros_build_lock(service, tmp_path):
    import json

    from d1env.models import DeploymentRequest
    started = service.preview(DeploymentRequest()).plan
    assert started is not None
    job = service.start(started.plan_id, "source-report")
    assert wait_done(service.engine, job.job_id).state == "SUCCEEDED"
    service.root_dir = tmp_path
    directory = tmp_path / "docs/build"
    directory.mkdir(parents=True)
    lock = {"image_id": "fixture-only", "robot_sdk_invoked": False}
    (directory / "ROS_PROBE_LOCK.json").write_text(json.dumps(lock))
    report = service.report(job.job_id)["report"]
    assert report["source_locks"]["ros_probe_build"] == lock


def test_event_read_does_not_compete_with_current_health_probe(authenticated, service, monkeypatch):
    from d1env.planner import resolve
    client, _headers = authenticated
    plan = resolve(request(), software_host(), software_catalog()).plan
    assert plan is not None
    job, _ = service.store.claim(plan, "events-read", lambda: None)
    def refuse_health(job_id):
        raise AssertionError("an event read must not inspect/lock Docker again")
    monkeypatch.setattr(service.engine, "get", refuse_health)
    response = client.get(f"/api/jobs/{job.job_id}/events")
    assert response.status_code == 200 and response.json()
