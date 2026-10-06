import multiprocessing
import threading
from pathlib import Path

import pytest
from test_jobs import plan, wait_state

from d1env.jobs.engine import JobEngine
from d1env.jobs.mock import MockExecutor
from d1env.jobs.store import Store


def _interruptible_process(db_path, work_dir, state, output):
    engine = JobEngine(Store(Path(db_path)), Path(work_dir), MockExecutor(delay_s=0.4))
    job = engine.submit(plan(), "process-before-crash")
    wait_state(engine, job.job_id, state)
    output.put(job.job_id)
    # The actual worker remains live while the parent verifies the lock, then kills this process.
    threading.Event().wait(30)


@pytest.mark.parametrize("state", ["STARTING", "VERIFYING"])
def test_restart_marks_dead_worker_interrupted_with_inventory_and_never_restarts(tmp_path, state):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    db, work_dir = tmp_path / "jobs.sqlite3", tmp_path / "resources"
    child = context.Process(
        target=_interruptible_process, args=(str(db), str(work_dir), state, output)
    )
    try:
        child.start()
        job_id = output.get(timeout=10)
        recovered = JobEngine(Store(db), work_dir)
        assert recovered.reconcile_on_startup() == []
        assert recovered.get(job_id).state == state
        child.terminate()
        child.join(5)
        changed = recovered.reconcile_on_startup()
        assert [job.job_id for job in changed] == [job_id]
        assert changed[0].state == "INTERRUPTED"
        assert changed[0].error_code == "WORKER_INTERRUPTED"
        events = recovered.get_events(job_id)
        inventory = [event for event in events if event.event_type == "inventory"]
        assert len(inventory) == 1
        assert inventory[0].mode == inventory[0].origin == "mock"
        assert inventory[0].evidence["auto_restart"] is False
        assert inventory[0].evidence["resources"]
        assert list((work_dir / job_id).glob("*.mock"))
        assert recovered.reconcile_on_startup() == []
        assert recovered.get(job_id).state == "INTERRUPTED"
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        output.close()
