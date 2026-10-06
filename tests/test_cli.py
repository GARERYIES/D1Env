import json

from typer.testing import CliRunner

from d1env.cli import app
from d1env.models import DeploymentRequest


def test_cli_ui_same_shared_resolution(service,monkeypatch):
    monkeypatch.setattr("d1env.cli.get_service",lambda: service)
    response=CliRunner().invoke(app,["plan","--profile","unknown","--mode","real_readonly"])
    assert response.exit_code == 1
    assert json.loads(response.stdout) == service.preview(DeploymentRequest(mode="real_readonly",profile_id="unknown")).model_dump(mode="json")


def test_cli_doctor_keeps_unknown_scope(service,monkeypatch):
    monkeypatch.setattr("d1env.cli.get_service",lambda: service)
    response=CliRunner().invoke(app,["doctor"])
    assert response.exit_code == 0
    assert json.loads(response.stdout)["telemetry"]["status"] == "UNKNOWN"


def test_cli_has_no_motion_command():
    assert CliRunner().invoke(app,["arm"]).exit_code != 0


def test_occupied_port_is_reported_without_rebinding_or_killing(service,monkeypatch):
    import socket
    monkeypatch.setattr("d1env.cli.get_service",lambda: service)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1",0))
        listener.listen()
        port = listener.getsockname()[1]
        response = CliRunner().invoke(app,["ui","--demo","--no-browser","--port",str(port)])
        assert response.exit_code == 1
        assert "端口已占用" in response.output
        assert listener.getsockname()[1] == port
