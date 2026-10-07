from typer.testing import CliRunner

from d1env.cli import app


def test_cli_imports_only_via_trusted_shared_service(service, monkeypatch, tmp_path):
    monkeypatch.setattr("d1env.cli.get_service", lambda: service)
    bundle = tmp_path / "release-image.bundle"
    bundle.write_bytes(b"boundary fixture only")
    observed = []
    def importer(path):
        observed.append(path)
        return {"status": "imported", "software_scope_only": True}
    monkeypatch.setattr(service, "import_ros_image", importer)
    result = CliRunner().invoke(app, ["import-image", str(bundle)])
    assert result.exit_code == 0 and '"software_scope_only": true' in result.output
    assert observed == [bundle]


def test_cli_import_error_exits_failure_instead_of_claiming_success(service, monkeypatch, tmp_path):
    monkeypatch.setattr("d1env.cli.get_service", lambda: service)
    def blocked(path):
        raise ValueError("OFFLINE_IMPORT_BLOCKED: 缺少匹配的发行记录")
    monkeypatch.setattr(service, "import_ros_image", blocked)
    result = CliRunner().invoke(app, ["import-image", str(tmp_path / "image.bundle")])
    assert result.exit_code == 1 and "OFFLINE_IMPORT_BLOCKED" in result.output
