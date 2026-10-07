import os
import stat
from pathlib import Path

import pytest


def test_mac_cli_without_known_desktop_is_explicitly_unverified(tmp_path):
    from d1env.docker.endpoint import resolve_endpoint
    with pytest.raises(ValueError, match="DOCKER_APP_UNVERIFIED"):
        resolve_endpoint(system="Darwin", which=lambda name: str(tmp_path / "docker"),
                         home=tmp_path, app_path=tmp_path / "missing.app")


def test_desktop_cli_without_path_uses_only_fixed_user_socket(tmp_path):
    from d1env.docker.endpoint import resolve_endpoint
    app = tmp_path / "Applications/Docker.app"
    cli = app / "Contents/Resources/bin/docker"
    cli.parent.mkdir(parents=True)
    cli.write_text("fixture")
    cli.chmod(0o755)
    seen = []
    endpoint = resolve_endpoint(system="Darwin", which=lambda name: None, home=tmp_path,
                                app_path=app, verify_app=lambda path: seen.append(path))
    assert endpoint.prefix == (str(cli), "--host", f"unix://{tmp_path}/.docker/run/docker.sock")
    assert endpoint.local is True
    assert seen == [app]


def test_desktop_wrong_signature_cannot_supply_docker_cli(tmp_path):
    from d1env.docker.endpoint import resolve_endpoint
    app = tmp_path / "Docker.app"
    app.mkdir()
    def reject(path):
        raise ValueError("SIGNATURE_REJECTED")
    with pytest.raises(ValueError, match="SIGNATURE_REJECTED"):
        resolve_endpoint(system="Darwin", which=lambda name: None, home=tmp_path,
                         app_path=app, verify_app=reject)


@pytest.mark.parametrize("kind", ["regular", "symlink", "foreign_owner"])
def test_local_socket_cannot_be_redirected_or_fabricated(tmp_path, monkeypatch, kind):
    from d1env.docker.endpoint import resolve_endpoint
    app = tmp_path / "Docker.app"
    cli = app / "Contents/Resources/bin/docker"
    cli.parent.mkdir(parents=True)
    cli.write_text("fixture")
    cli.chmod(0o755)
    path = tmp_path / ".docker/run/docker.sock"
    path.parent.mkdir(parents=True)
    if kind == "symlink":
        destination = tmp_path / "other.sock"
        destination.touch()
        path.symlink_to(destination)
    else:
        path.touch()
    if kind == "foreign_owner":
        original = Path.lstat
        def foreign(path_self, *args, **kwargs):
            observed = original(path_self, *args, **kwargs)
            if path_self == path:
                values = list(observed)
                values[0] = stat.S_IFSOCK | 0o600
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return observed
        monkeypatch.setattr(Path, "lstat", foreign)
    with pytest.raises(ValueError, match="DOCKER_ENDPOINT_UNSAFE"):
        resolve_endpoint(system="Darwin", which=lambda name: None, home=tmp_path,
                         app_path=app, verify_app=lambda path: None)


def test_endpoint_has_no_web_supplied_remote_parameters():
    from d1env.docker.endpoint import LocalDockerEndpoint
    with pytest.raises(ValueError, match="DOCKER_ENDPOINT_UNSAFE"):
        LocalDockerEndpoint(("docker", "--host", "tcp://example.com:2375"), None, True)


def test_docker_execution_and_readonly_probe_share_the_verified_entry(tmp_path, monkeypatch):
    import json
    import sys

    from d1env.docker.client import INFO_FORMAT, DockerClient
    from d1env.docker.endpoint import LocalDockerEndpoint
    from d1env.doctor import DOCKER_INFO
    from d1env.process import ProbeRunner

    cli = tmp_path / "Docker.app/Contents/Resources/bin/docker"
    cli.parent.mkdir(parents=True)
    cli.write_text(f"#!{sys.executable}\nimport json,os,sys\n"
                   "print(json.dumps({'argv':sys.argv[1:],'remote':os.environ.get('DOCKER_HOST')}))\n")
    cli.chmod(0o755)
    endpoint = LocalDockerEndpoint((str(cli), "--host", f"unix://{tmp_path}/.docker/run/docker.sock"), None, True)
    monkeypatch.setattr("d1env.docker.client.resolve_endpoint", lambda: endpoint, raising=False)
    monkeypatch.setattr("d1env.process.resolve_endpoint", lambda: endpoint, raising=False)
    monkeypatch.setenv("DOCKER_HOST", "tcp://untrusted.invalid:2375")
    for result in [DockerClient().run(("info", "--format", INFO_FORMAT)), ProbeRunner().run(DOCKER_INFO)]:
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["argv"][:2] == list(endpoint.prefix[1:])
        assert payload["remote"] is None


def test_path_cli_without_legacy_socket_uses_desktop_user_socket(tmp_path):
    import socket
    import tempfile

    from d1env.docker.endpoint import resolve_endpoint
    with tempfile.TemporaryDirectory(prefix="d1-") as short_path:
        tmp_path = Path(short_path).resolve()
        app = tmp_path / 'Docker.app'
        cli = app / 'Contents/Resources/bin/docker'
        cli.parent.mkdir(parents=True)
        cli.write_text('fixture')
        cli.chmod(0o755)
        sock = tmp_path / '.docker/run/docker.sock'
        sock.parent.mkdir(parents=True)
        connection = socket.socket(socket.AF_UNIX)
        try:
            connection.bind(str(sock))
            result = resolve_endpoint(system='Darwin', which=lambda name: '/usr/local/bin/docker',
                                      home=tmp_path, app_path=app, default_socket=tmp_path/'absent.sock',
                                      verify_app=lambda path: None)
            assert result.prefix[0] == str(cli)
            assert result.prefix[1:] == ('--host', f'unix://{sock}')
        finally:
            connection.close()


def signed_fixture(tmp_path):
    app = tmp_path / 'Docker.app'
    for name in ['Info.plist', 'Resources/bin/docker', '_CodeSignature/CodeResources']:
        path = app / 'Contents' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    return app


def test_signature_cache_rechecks_directory_permissions(tmp_path, monkeypatch):
    import subprocess

    from d1env.docker.endpoint import verify_desktop_app
    app = signed_fixture(tmp_path)
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kw: subprocess.CompletedProcess(args, 0))
    verify_desktop_app(app)
    app.chmod(0o775)
    with pytest.raises(ValueError, match='DOCKER_APP_UNVERIFIED'):
        verify_desktop_app(app)


def test_signature_cache_rechecks_changed_nested_component(tmp_path, monkeypatch):
    import subprocess

    from d1env.docker.endpoint import verify_desktop_app
    app = signed_fixture(tmp_path)
    nested = app / 'Contents/Resources/component'
    nested.write_text('original')
    calls = []
    def observed(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, 'run', observed)
    verify_desktop_app(app)
    verify_desktop_app(app)
    assert len(calls) == 2
    nested.write_text('changed')
    verify_desktop_app(app)
    assert len(calls) == 4


def test_application_outer_symlink_is_rejected(tmp_path, monkeypatch):
    import subprocess

    from d1env.docker.endpoint import verify_desktop_app
    app = signed_fixture(tmp_path)
    linked = tmp_path / 'Linked.app'
    linked.symlink_to(app)
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kw: subprocess.CompletedProcess(args, 0))
    with pytest.raises(ValueError, match='DOCKER_APP_UNVERIFIED'):
        verify_desktop_app(linked)


def test_concurrent_cold_signature_observations_share_one_verification(tmp_path, monkeypatch):
    import subprocess
    import threading
    import time

    from d1env.docker.endpoint import verify_desktop_app
    app = signed_fixture(tmp_path)
    barrier = threading.Barrier(2)
    calls = []
    def signature(*args, **kwargs):
        calls.append(args)
        time.sleep(0.02)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, 'run', signature)
    def read():
        barrier.wait()
        verify_desktop_app(app)
    threads = [threading.Thread(target=read) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert len(calls) == 2


def test_mac_path_and_legacy_regular_file_cannot_bypass_official_signature(tmp_path):
    from d1env.docker.endpoint import resolve_endpoint
    app = signed_fixture(tmp_path)
    legacy = tmp_path / 'legacy.sock'
    legacy.touch()
    def reject(path):
        raise ValueError('SIGNATURE_REJECTED')
    with pytest.raises(ValueError, match='SIGNATURE_REJECTED'):
        resolve_endpoint(system='Darwin', which=lambda name: '/usr/local/bin/docker', home=tmp_path,
                         app_path=app, default_socket=legacy, verify_app=reject)


def test_app_change_during_signature_verification_blocks_cli(tmp_path, monkeypatch):
    import subprocess

    from d1env.docker.endpoint import verify_desktop_app
    app = signed_fixture(tmp_path)
    def changed(*args, **kwargs):
        (app/'Contents/Resources/changed-component').write_text('changed during verification')
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, 'run', changed)
    with pytest.raises(ValueError, match='DOCKER_APP_UNVERIFIED'):
        verify_desktop_app(app)
