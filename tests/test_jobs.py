import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from d1env.jobs.engine import InvalidPlan, JobEngine
from d1env.jobs.mock import MockExecutor
from d1env.jobs.store import JobConflict, Store
from d1env.models import DeploymentPlan, Operation

TERMINAL = {"SUCCEEDED", "BLOCKED", "FAILED", "CANCELLED", "INTERRUPTED"}


def plan(plan_id="plan-a", *, failure=False, extra_evidence=(), timeout_s=5.0):
    ids = ["preflight", "acquire", "configure", "start", "verify_failure" if failure else "verify"]
    return DeploymentPlan(
        plan_id=plan_id,
        mode="mock",
        target_id="local",
        profile_id="demo",
        operations=tuple(
            Operation(operation_id=step, label=f"MOCK {step}", timeout_s=timeout_s) for step in ids
        ),
        required_evidence=("mock_ready", *extra_evidence),
        verified_scope="mock",
        profile_revision="demo-v1",
        config_digest="demo-v1",
    )


def wait_done(engine, job_id, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = engine.get(job_id)
        if snapshot.state in TERMINAL:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("worker did not finish")


def wait_state(engine, job_id, state, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = engine.get(job_id)
        if snapshot.state == state:
            return snapshot
        if snapshot.state in TERMINAL:
            raise AssertionError(f"job ended at {snapshot.state} before {state}")
        time.sleep(0.005)
    raise AssertionError(f"worker never reached {state}")


def make_engine(tmp_path, delay=0.01):
    store = Store(tmp_path / "jobs.sqlite3")
    return JobEngine(store, tmp_path / "resources", MockExecutor(delay_s=delay)), store


def test_success_events_survive_new_store_and_only_verify_mock_scope(tmp_path):
    engine, store = make_engine(tmp_path)
    submitted = engine.submit(plan(), "once")
    result = wait_done(engine, submitted.job_id)
    assert result.state == "SUCCEEDED"
    assert result.mode == result.verified_scope == "mock"
    persisted = Store(store.path).get_events(result.job_id)
    assert [event.seq for event in persisted] == list(range(1, len(persisted) + 1))
    assert {event.mode for event in persisted} == {"mock"}
    assert {event.origin for event in persisted} == {"mock"}
    assert any(event.evidence.get("mock_ready") is True for event in persisted)
    assert [event.evidence["state"] for event in persisted if event.event_type == "state"] == [
        "PLANNED",
        "PREFLIGHT",
        "ACQUIRING",
        "CONFIGURING",
        "STARTING",
        "VERIFYING",
        "SUCCEEDED",
    ]
    assert Store(store.path).get_plan("plan-a") == plan()


def test_step_failure_is_labelled_fault_injection_with_evidence(tmp_path):
    engine, store = make_engine(tmp_path)
    job = engine.submit(plan(failure=True), "injected")
    failed = wait_done(engine, job.job_id)
    assert failed.state == "FAILED"
    assert failed.error_code == "MOCK_READINESS_FAILED"
    failures = [
        event for event in store.get_events(job.job_id) if event.event_type == "operation_failed"
    ]
    assert len(failures) == 1
    assert failures[0].evidence["fault_injection"] is True
    assert failures[0].evidence["mock_ready"] is False
    assert "<script>window.__d1env_injected=true</script>" in failures[0].message


def test_same_key_always_binds_same_plan_and_success_reused_with_new_key(tmp_path):
    engine, store = make_engine(tmp_path)
    job = engine.submit(plan(), "first")
    assert engine.submit(plan(), "first").job_id == job.job_id
    assert engine.submit(plan(), "second").job_id == job.job_id
    with pytest.raises(JobConflict) as error:
        engine.submit(plan("other"), "first")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    wait_done(engine, job.job_id)
    assert engine.submit(plan(), "third").job_id == job.job_id
    with pytest.raises(JobConflict):
        engine.submit(plan("other"), "second")
    assert len(store.list_jobs()) == 1


def test_failed_key_cannot_change_plan_and_only_new_key_retries(tmp_path):
    engine, store = make_engine(tmp_path)
    failed_plan = plan(failure=True)
    job = engine.submit(failed_plan, "failed-once")
    assert wait_done(engine, job.job_id).state == "FAILED"
    assert engine.submit(failed_plan, "failed-once").job_id == job.job_id
    with pytest.raises(JobConflict) as error:
        engine.submit(plan("other"), "failed-once")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    retry = engine.submit(failed_plan, "retry-explicit")
    assert retry.job_id != job.job_id
    assert wait_done(engine, retry.job_id).state == "FAILED"
    assert len(store.list_jobs()) == 2


def test_concurrent_threads_reuse_worker_and_reject_other_active_plan(tmp_path):
    engine, store = make_engine(tmp_path, delay=0.1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda index: engine.submit(plan(), f"request-{index}"), range(8)))
    assert len({job.job_id for job in jobs}) == 1
    with pytest.raises(JobConflict) as error:
        engine.submit(plan("other"), "other")
    assert error.value.code == "TARGET_BUSY"
    assert wait_done(engine, jobs[0].job_id).state == "SUCCEEDED"
    assert len(store.list_jobs()) == 1
    starts = [
        event
        for event in store.get_events(jobs[0].job_id)
        if event.event_type == "operation_started"
    ]
    assert len(starts) == 5


def _submit_in_process(db_path, work_dir, start, output, key):
    engine = JobEngine(Store(Path(db_path)), Path(work_dir), MockExecutor(delay_s=0.2))
    start.wait(5)
    job = engine.submit(plan(), key)
    output.put(job.job_id)
    wait_done(engine, job.job_id)


def test_two_actual_processes_cannot_start_second_worker(tmp_path):
    context = multiprocessing.get_context("spawn")
    start, output = context.Event(), context.Queue()
    db, work_dir = tmp_path / "jobs.sqlite3", tmp_path / "resources"
    Store(db)
    children = [
        context.Process(
            target=_submit_in_process, args=(str(db), str(work_dir), start, output, f"process-{i}")
        )
        for i in range(2)
    ]
    try:
        for child in children:
            child.start()
        start.set()
        ids = [output.get(timeout=10), output.get(timeout=10)]
        assert ids[0] == ids[1]
        for child in children:
            child.join(10)
            assert child.exitcode == 0
        store = Store(db)
        assert len(store.list_jobs()) == 1
        starts = [
            event for event in store.get_events(ids[0]) if event.event_type == "operation_started"
        ]
        assert len(starts) == 5
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(5)
        output.close()


def test_cancel_preserves_maps_bags_other_jobs_and_unowned_files(tmp_path):
    engine, store = make_engine(tmp_path, delay=0.15)
    user_map = tmp_path / "maps" / "lab.yaml"
    user_map.parent.mkdir()
    user_map.write_text("user map")
    other_job = tmp_path / "resources" / "other-job" / "other.mock"
    other_job.parent.mkdir(parents=True)
    other_job.write_text("another owner")
    job = engine.submit(plan(), "cancel")
    wait_state(engine, job.job_id, "CONFIGURING")
    own_dir = tmp_path / "resources" / job.job_id
    user_bag = own_dir / "user.bag"
    user_bag.write_text("user bag")
    assert list(own_dir.glob("*.mock"))
    engine.cancel(job.job_id)
    cancelled = wait_done(engine, job.job_id)
    assert cancelled.state == "CANCELLED"
    assert not list(own_dir.glob("*.mock"))
    assert user_map.read_text() == "user map"
    assert user_bag.read_text() == "user bag"
    assert other_job.read_text() == "another owner"
    assert any(event.event_type == "cleanup" for event in store.get_events(job.job_id))
    assert engine.cancel(job.job_id).state == "CANCELLED"


def test_cancel_request_from_second_engine_reaches_active_worker(tmp_path):
    engine, store = make_engine(tmp_path, delay=0.15)
    job = engine.submit(plan(), "cancel-other-process-view")
    wait_state(engine, job.job_id, "ACQUIRING")
    other = JobEngine(Store(store.path), tmp_path / "resources")
    other.cancel(job.job_id)
    assert wait_done(engine, job.job_id).state == "CANCELLED"


def test_required_readiness_evidence_must_exist_and_cannot_be_process_alive(tmp_path):
    engine, store = make_engine(tmp_path)
    job = engine.submit(plan(extra_evidence=("freshness_verified",)), "missing-evidence")
    final = wait_done(engine, job.job_id)
    assert final.state == "FAILED"
    assert final.error_code == "READINESS_EVIDENCE_MISSING"
    assert any(
        event.evidence.get("missing_evidence") == ["freshness_verified"]
        for event in store.get_events(job.job_id)
    )
    unsafe = plan("unsafe").model_copy(update={"required_evidence": ("process_alive",)})
    with pytest.raises(InvalidPlan):
        engine.submit(unsafe, "unsafe")


@pytest.mark.parametrize("malformed", ["false", 1, {}, []])
def test_readiness_requires_literal_boolean_true(tmp_path, malformed):
    class MalformedReady(MockExecutor):
        def execute(self, operation, context):
            result = super().execute(operation, context)
            if operation.operation_id == "verify":
                return result.model_copy(update={"evidence":{"mock_ready":malformed}})
            return result
    store = Store(tmp_path / "jobs.sqlite3")
    engine = JobEngine(store, tmp_path / "resources", MalformedReady(delay_s=0))
    job = engine.submit(plan(), "malformed-evidence")
    assert wait_done(engine, job.job_id).state == "FAILED"


def test_operation_timeout_is_enforced_without_continuing_steps(tmp_path):
    engine, store = make_engine(tmp_path, delay=0.2)
    job = engine.submit(plan(timeout_s=0.025), "deadline")
    final = wait_done(engine, job.job_id)
    assert final.state == "FAILED"
    assert final.error_code == "OPERATION_TIMEOUT"
    starts = [
        event for event in store.get_events(job.job_id) if event.event_type == "operation_started"
    ]
    assert [event.operation_id for event in starts] == ["preflight"]


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "real_readonly"},
        {"operations": (Operation(operation_id="../../escape", label="bad"),)},
        {"operations": ()},
    ],
)
def test_non_mock_or_unknown_operations_never_create_job(tmp_path, change):
    engine, store = make_engine(tmp_path)
    with pytest.raises(InvalidPlan):
        engine.submit(plan().model_copy(update=change), "invalid")
    assert store.list_jobs() == []


def test_plan_id_cannot_be_rebound_to_changed_content(tmp_path):
    engine, store = make_engine(tmp_path)
    store.save_plan(plan())
    with pytest.raises(JobConflict) as error:
        store.save_plan(plan().model_copy(update={"config_digest": "different"}))
    assert error.value.code == "PLAN_ID_CONFLICT"
    assert store.get_plan("plan-a").config_digest == "demo-v1"
    with pytest.raises(KeyError):
        engine.get("unknown")


def test_slow_cancel_check_does_not_turn_completed_delay_into_error(tmp_path):
    from d1env.models import ExecutionContext

    def cancel_check():
        time.sleep(0.02)
        return False

    context = ExecutionContext(
        job_id="test-local",
        target_id="local",
        mode="mock",
        work_dir=tmp_path,
        is_cancelled=cancel_check,
        emit=lambda event: None,
    )
    result = MockExecutor(delay_s=0.01).execute(
        Operation(operation_id="preflight", label="MOCK"), context
    )
    assert result.status == "succeeded"


@pytest.mark.parametrize("change", ["reordered", "missing_verify", "non_reversible"])
def test_incomplete_or_out_of_order_plan_cannot_claim_readiness(tmp_path, change):
    engine, store = make_engine(tmp_path)
    original = plan()
    if change == "reordered":
        operations = tuple(reversed(original.operations))
    elif change == "missing_verify":
        operations = original.operations[:-1]
    else:
        operations = (
            original.operations[0].model_copy(update={"reversible": False}),
            *original.operations[1:],
        )
    with pytest.raises(InvalidPlan):
        engine.submit(original.model_copy(update={"operations": operations}), "invalid-order")
    assert store.list_jobs() == []


def test_worker_start_failure_is_persisted_interrupted_and_releases_target(tmp_path, monkeypatch):
    import threading

    engine, store = make_engine(tmp_path)
    original_start = threading.Thread.start

    def refuse_start(self):
        raise RuntimeError("thread resources unavailable")

    monkeypatch.setattr(threading.Thread, "start", refuse_start)
    with pytest.raises(JobConflict) as error:
        engine.submit(plan(), "start-failed")
    assert error.value.code == "WORKER_START_FAILED"
    [interrupted] = store.list_jobs()
    assert interrupted.state == "INTERRUPTED"
    assert interrupted.error_code == "WORKER_START_FAILED"
    monkeypatch.setattr(threading.Thread, "start", original_start)
    retry = engine.submit(plan(), "start-retry")
    assert retry.job_id != interrupted.job_id
    assert wait_done(engine, retry.job_id).state == "SUCCEEDED"
