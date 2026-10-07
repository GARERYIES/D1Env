import json
import os
import subprocess
import sys
from pathlib import Path

from d1env.jobs.store import Store


def test_standalone_cli_waits_until_mock_worker_finishes_before_exiting(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "D1ENV_ASSETS_DIR": str(root),
           "D1ENV_STATE_DIR": str(tmp_path)}
    planned = subprocess.run([sys.executable, "-m", "d1env.cli", "plan"],
        env=env, cwd=root, capture_output=True, text=True, timeout=30, check=False)
    assert planned.returncode == 0, planned.stderr
    plan_id = json.loads(planned.stdout)["plan"]["plan_id"]
    result = subprocess.run([sys.executable, "-m", "d1env.cli", "deploy", plan_id,
                            "--request-key", "standalone-process"],
        env=env, cwd=root, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    final = json.loads(result.stdout)
    assert final["state"] == "SUCCEEDED"
    persisted = Store(tmp_path / "jobs.sqlite").get_job(final["job_id"])
    assert persisted.state == "SUCCEEDED" and persisted.verified_scope == "mock"
