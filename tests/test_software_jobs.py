import time

import pytest
from test_software_plans import request, software_catalog, software_host

from d1env.jobs.engine import JobEngine
from d1env.jobs.store import JobConflict, Store
from d1env.models import OperationResult
from d1env.planner import resolve


class SoftwareProcessFixture:
    """Boundary double for Docker; SQLite, worker, plan and locks remain real."""
    def __init__(self):
        self.running = set()
        self.execute_count = 0
        self.ready = True

    def execute(self, operation, context):
        self.execute_count += 1
        if operation.operation_id == "start":
            self.running.add(context.job_id)
        return OperationResult(operation_id=operation.operation_id, status="succeeded", origin="docker",
                               evidence={"software_ready": self.ready} if operation.operation_id == "verify" else {},
                               message="软件通信测试边界替身，未运行 Docker")

    def verify_running(self, context, artifact):
        return OperationResult(operation_id="verify", origin="docker",
                               status="succeeded" if context.job_id in self.running else "failed",
                               evidence={"software_ready": context.job_id in self.running},
                               error_code=None if context.job_id in self.running else "SERVICES_MISSING",
                               message="只验证任务引擎重新检查行为")

    def cleanup(self, context):
        self.running.discard(context.job_id)
        return [context.job_id]

    def inventory(self, context):
        return {"resources": [], "remaining_owned": [context.job_id] if context.job_id in self.running else [],
                "untracked_resources": [], "inventory_complete": True}


def setup_engine(tmp_path):
    executor = SoftwareProcessFixture()
    store = Store(tmp_path / "jobs.sqlite")
    engine = JobEngine(store, tmp_path / "resources", software_executor=executor)
    plan = resolve(request(), software_host(), software_catalog()).plan
    assert plan
    return engine, store, executor, plan


def wait_done(engine, job_id):
    for _ in range(300):
        job = engine.get(job_id)
        if job.state in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"}:
            return job
        time.sleep(.01)
    raise AssertionError("worker did not finish")


def test_software_worker_persists_docker_origin_and_does_not_duplicate(tmp_path):
    engine, store, executor, plan = setup_engine(tmp_path)
    job = engine.submit(plan, "first")
    assert wait_done(engine, job.job_id).state == "SUCCEEDED"
    assert engine.submit(plan, "second").job_id == job.job_id
    assert executor.execute_count == 5
    assert store.get_job(job.job_id).verified_scope == "software"
    assert {event.origin for event in store.get_events(job.job_id)} == {"docker"}
    assert {event.mode for event in store.get_events(job.job_id)} == {"software_test"}


def test_historical_success_fails_when_actual_services_are_gone(tmp_path):
    engine, store, executor, plan = setup_engine(tmp_path)
    first = engine.submit(plan, "first")
    assert wait_done(engine, first.job_id).state == "SUCCEEDED"
    executor.running.clear()
    assert engine.get(first.job_id).state == "FAILED"
    assert store.get_job(first.job_id).error_code == "SERVICES_MISSING"
    assert engine.submit(plan, "first").job_id == first.job_id
    retry = engine.submit(plan, "new-key")
    assert retry.job_id != first.job_id
    assert wait_done(engine, retry.job_id).state == "SUCCEEDED"


def test_stop_only_owned_software_then_new_key_redeploys(tmp_path):
    engine, _store, executor, plan = setup_engine(tmp_path)
    first = engine.submit(plan, "first")
    assert wait_done(engine, first.job_id).state == "SUCCEEDED"
    executor.running.add("foreign-owner")
    assert engine.stop(first.job_id).state == "CANCELLED"
    assert executor.running == {"foreign-owner"}
    assert engine.stop(first.job_id).state == "CANCELLED"
    second = engine.submit(plan, "after-stop")
    assert second.job_id != first.job_id
    assert wait_done(engine, second.job_id).state == "SUCCEEDED"


def test_non_boolean_software_readiness_fails_and_cleans_up(tmp_path):
    engine, _store, executor, plan = setup_engine(tmp_path)
    executor.ready = "true"
    job = engine.submit(plan, "bad-ready")
    final = wait_done(engine, job.job_id)
    assert final.state == "FAILED"
    assert final.error_code == "OPERATION_EVIDENCE_MISSING"
    assert not executor.running


def test_software_restart_records_real_inventory_without_restarting(tmp_path):
    engine, store, executor, plan = setup_engine(tmp_path)
    job, created = store.claim(plan, "crashed", lambda: None)
    assert created
    executor.running.add(job.job_id)
    store.transition(job.job_id, "STARTING", "interrupted boundary fixture")
    changed = engine.reconcile_on_startup()
    assert [item.state for item in changed] == ["INTERRUPTED"]
    assert executor.execute_count == 0
    event = next(event for event in store.get_events(job.job_id) if event.event_type == "inventory")
    assert event.origin == "docker" and event.evidence["auto_restart"] is False
    assert event.evidence["remaining_owned"] == [job.job_id]


def test_executor_exception_cleans_owned_resources_before_failure(tmp_path):
    engine, _store, executor, plan = setup_engine(tmp_path)
    execute = executor.execute
    def fail_verify(operation, context):
        if operation.operation_id == "verify":
            raise OSError("daemon interrupted")
        return execute(operation, context)
    executor.execute = fail_verify
    job = engine.submit(plan, "exception")
    assert wait_done(engine, job.job_id).state == "FAILED"
    assert not executor.running


def test_cancel_cleanup_error_ends_failed_with_preserved_inventory(tmp_path):
    engine, store, executor, plan = setup_engine(tmp_path)
    job, _ = store.claim(plan, "cancel-cleanup", lambda: None)
    executor.running.add(job.job_id)
    store.request_cancel(job.job_id)
    def refuse_cleanup(context):
        raise OSError("ownership changed")
    executor.cleanup = refuse_cleanup
    class Lease:
        def release(self):
            pass
    engine._cancel_worker(job.job_id, Lease())
    final = store.get_job(job.job_id)
    assert final.state == "FAILED" and final.error_code == "CLEANUP_INCOMPLETE"
    assert job.job_id in executor.running


@pytest.mark.parametrize("inventory", [
    {"remaining_owned": [], "inventory_complete": False, "untracked_resources": []},
    {"remaining_owned": [], "inventory_complete": True, "untracked_resources": ["unregistered-id"]},
    {"remaining_owned": []},
])
def test_stop_cannot_claim_complete_without_known_empty_inventory(tmp_path, inventory):
    engine, _store, executor, plan = setup_engine(tmp_path)
    job = engine.submit(plan, "stop-unknown")
    assert wait_done(engine, job.job_id).state == "SUCCEEDED"
    executor.inventory = lambda context: inventory
    final = engine.stop(job.job_id)
    assert final.state == "FAILED" and final.error_code == "CLEANUP_INCOMPLETE"


def test_current_health_is_unknown_while_target_is_busy(tmp_path):
    from d1env.jobs.engine import _TargetLock
    engine, store, _executor, plan = setup_engine(tmp_path)
    job = engine.submit(plan, "health-busy")
    assert wait_done(engine, job.job_id).state == "SUCCEEDED"
    assert engine.get(job.job_id).current_software_ready is True
    lease = _TargetLock(engine._lock_path("local"))
    try:
        current = engine.get(job.job_id)
        assert current.state == "SUCCEEDED"  # Recorded deployment outcome remains intact.
        assert current.current_software_ready is None
        assert current.current_health_evidence["code"] == "TARGET_BUSY"
        assert store.get_job(job.job_id).current_software_ready is None
    finally:
        lease.release()


@pytest.mark.parametrize("history", ["stale", "interrupted", "unknown_inventory"])
def test_new_task_is_blocked_until_previous_software_resources_are_cleaned(tmp_path, history):
    engine, store, executor, plan = setup_engine(tmp_path)
    first = engine.submit(plan, "first-resource-owner")
    assert wait_done(engine, first.job_id).state == "SUCCEEDED"
    if history == "stale":
        original_verify = executor.verify_running
        executor.verify_running = lambda context, artifact: OperationResult(
            operation_id="verify", status="failed", origin="docker", error_code="ROS_PROBE_NOT_READY",
            message="stale boundary fixture", evidence={"software_ready": False})
        assert engine.get(first.job_id).state == "FAILED"
        executor.verify_running = original_verify
    elif history == "interrupted":
        # Persistent recovery state with previously created resources, without auto restart.
        store.reassess_software(first.job_id, "FAILED", "interrupted fixture")
    else:
        store.reassess_software(first.job_id, "FAILED", "unknown fixture")
        original_inventory = executor.inventory
        executor.inventory = lambda context: {"inventory_complete": False, "remaining_owned": []}
    with pytest.raises(JobConflict, match="遗留") as error:
        engine.submit(plan, "new-resource-owner")
    assert error.value.code == "SOFTWARE_RESOURCES_PENDING"
    assert len(store.list_jobs()) == 1 and executor.execute_count == 5
    assert executor.running == {first.job_id}
    if history == "unknown_inventory":
        executor.inventory = original_inventory
    assert engine.stop(first.job_id).state == "CANCELLED"
    second = engine.submit(plan, "new-resource-owner")
    assert second.job_id != first.job_id
    assert wait_done(engine, second.job_id).state == "SUCCEEDED"


def test_interrupted_real_inventory_prevents_duplicate_recovery_deployment(tmp_path):
    engine, store, executor, plan = setup_engine(tmp_path)
    prior, _ = store.claim(plan, "dead-worker", lambda: None)
    executor.running.add(prior.job_id)
    engine.work_dir.joinpath(prior.job_id).mkdir(parents=True)
    store.transition(prior.job_id, "STARTING", "worker was interrupted")
    assert engine.reconcile_on_startup()[0].state == "INTERRUPTED"
    with pytest.raises(JobConflict) as error:
        engine.submit(plan, "retry-after-crash")
    assert error.value.code == "SOFTWARE_RESOURCES_PENDING"
    assert len(store.list_jobs()) == 1 and executor.execute_count == 0
