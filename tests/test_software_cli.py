import json

from test_software_jobs import SoftwareProcessFixture, wait_done
from test_software_plans import software_catalog, software_host
from typer.testing import CliRunner

from d1env.cli import app


def test_cli_software_plan_deploy_stop_share_service(service, monkeypatch):
    monkeypatch.setattr("d1env.cli.get_service", lambda: service)
    monkeypatch.setattr("d1env.service.inspect_host", lambda *args: software_host())
    service.catalog = software_catalog()
    service.engine._software_executor = SoftwareProcessFixture()
    runner = CliRunner()
    preview = runner.invoke(app, ["plan", "--profile", "ros-probe", "--mode", "software_test"])
    assert preview.exit_code == 0
    plan_id = json.loads(preview.stdout)["plan"]["plan_id"]
    deployed = runner.invoke(app, ["deploy", plan_id, "--request-key", "cli-software"])
    assert deployed.exit_code == 0
    job_id = json.loads(deployed.stdout)["job_id"]
    assert wait_done(service.engine, job_id).state == "SUCCEEDED"
    stopped = runner.invoke(app, ["stop", job_id])
    assert stopped.exit_code == 0 and json.loads(stopped.stdout)["state"] == "CANCELLED"
