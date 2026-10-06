import time

import pytest


def test_no_arm_or_arbitrary_exec_endpoint(authenticated):
    client,headers=authenticated
    for path in ["/api/arm","/api/move","/api/exec"]:
        assert client.post(path,json={},headers=headers).status_code == 404


@pytest.mark.parametrize("payload", [
    {"target_id":"192.168.1.10"}, {"host_facts":{"os_name":"Linux"}},
    {"shell":"id"}, {"mode":"real"}, {"profile_id":"../../evil"},
])
def test_browser_cannot_forge_target_facts_or_commands(authenticated,payload):
    client,headers=authenticated
    assert client.post("/api/plans",json=payload,headers=headers).status_code == 422


def test_hardware_blockers_and_mock_scope(authenticated):
    client,headers=authenticated
    response=client.post("/api/plans",json={"mode":"real_readonly","profile_id":"unknown"},headers=headers)
    assert response.status_code == 200
    assert response.json()["plan"] is None
    assert response.json()["blockers"][0]["code"] == "PROFILE_UNVERIFIED"
    doctor=client.post("/api/doctor",json={},headers=headers).json()
    assert doctor["telemetry"]["battery_percent"] is None
    assert doctor["telemetry"]["status"] == "UNKNOWN"
    plan=client.post("/api/plans",json={},headers=headers).json()["plan"]
    data={"plan_id":plan["plan_id"],"idempotency_key":"web-key"}
    one=client.post("/api/jobs",json=data,headers=headers)
    two=client.post("/api/jobs",json=data,headers=headers)
    assert one.status_code == 200 and two.status_code == 200
    assert one.json()["job_id"] == two.json()["job_id"]
    jid=one.json()["job_id"]
    for _ in range(100):
        job=client.get(f"/api/jobs/{jid}").json()
        if job["state"] == "SUCCEEDED": break
        time.sleep(.05)
    assert job["state"] == "SUCCEEDED" and job["verified_scope"] == "mock"
    events=client.get(f"/api/jobs/{jid}/events").json()
    assert all(e["mode"] == "mock" and e["origin"] == "mock" for e in events)
    exported=client.post("/api/reports",json={"job_id":jid,"mask_identifiers":True},headers=headers)
    assert exported.status_code == 200
    assert exported.json()["report"]["mode"] == "mock"


def test_no_submitted_plan_body_or_arbitrary_workdir(authenticated):
    client,headers=authenticated
    assert client.post("/api/jobs",json={"plan_id":"x","idempotency_key":"y","work_dir":"/tmp"},headers=headers).status_code == 422
