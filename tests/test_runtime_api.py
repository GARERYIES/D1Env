import pytest


class PreparationBoundary:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {"environment_ready": None, "scope": "runtime_environment", "task": None}

    def prepare(self, key):
        self.calls.append(("prepare", key))
        return {"task_id": "a" * 32, "scope": "runtime_environment", "environment_ready": None}

    def get(self, task_id):
        self.calls.append(("get", task_id))
        return {"task_id": task_id, "state": "WAITING_USER", "user_action": "accept_license"}

    def continue_task(self, task_id, action):
        self.calls.append(("continue", task_id, action))
        return {"task_id": task_id, "state": "RUNNING"}

    def cancel(self, task_id):
        self.calls.append(("cancel", task_id))
        return {"task_id": task_id, "state": "CANCELLED"}


@pytest.fixture
def preparation(service):
    manager = PreparationBoundary()
    service._runtime_setup = manager
    return manager


def test_prepare_routes_use_shared_manager_without_install_arguments(authenticated, preparation):
    client, headers = authenticated
    assert client.get("/api/runtime/status").json()["environment_ready"] is None
    assert client.post("/api/runtime/prepare", headers=headers, json={"request_key": "one-request-123"}).status_code == 200
    task_id = "a" * 32
    assert client.get(f"/api/runtime/tasks/{task_id}").json()["user_action"] == "accept_license"
    assert client.post(f"/api/runtime/tasks/{task_id}/continue", headers=headers,
                       json={"action": "accept_license"}).status_code == 200
    assert client.post(f"/api/runtime/tasks/{task_id}/cancel", headers=headers, json={}).status_code == 200
    assert preparation.calls == [("status",), ("prepare", "one-request-123"), ("get", task_id),
                                 ("continue", task_id, "accept_license"), ("cancel", task_id)]


@pytest.mark.parametrize("payload", [
    {"request_key": "request-123", "url": "https://evil.invalid/install"},
    {"request_key": "request-123", "path": "/Applications/user.app"},
    {"request_key": "request-123", "command": "sudo curl | sh"},
    {"request_key": "bad;key"},
])
def test_prepare_rejects_injected_install_source_or_command(authenticated, preparation, payload):
    client, headers = authenticated
    assert client.post("/api/runtime/prepare", headers=headers, json=payload).status_code == 422
    assert preparation.calls == []


def test_prepare_mutations_require_session_origin_and_csrf(web_client, authenticated, preparation):
    client, headers = authenticated
    for supplied in [{}, {"Origin": "https://evil.invalid"}, {"Origin": headers["Origin"]}]:
        response = client.post("/api/runtime/prepare", json={"request_key": "request-123"}, headers=supplied)
        assert response.status_code == 403
    assert preparation.calls == []


def test_runtime_status_requires_a_session(web_client, preparation):
    assert web_client.get("/api/runtime/status").status_code == 401
    assert preparation.calls == []


def test_continue_only_accepts_fixed_user_actions(authenticated, preparation):
    client, headers = authenticated
    for payload in [{"action": "install-anything"}, {"action": "accept_license", "password": "never-read"}]:
        assert client.post(f"/api/runtime/tasks/{'a'*32}/continue", headers=headers, json=payload).status_code == 422
    assert preparation.calls == []


def test_cancel_cannot_smuggle_install_arguments(authenticated, preparation):
    client, headers = authenticated
    assert client.post(f"/api/runtime/tasks/{'a'*32}/cancel", headers=headers,
                       json={'command': 'sudo install'}).status_code == 422
    assert preparation.calls == []


@pytest.mark.parametrize('mutation', ['wrong_id', 'wrong_arch', 'wrong_source', 'timeout', 'malformed', 'matching'])
def test_service_image_observation_never_reports_unverified_image_ready(service, monkeypatch, mutation):
    import json

    from d1env.docker.client import DockerCommand
    metadata = service.ros_image_metadata()['trusted_bundle']
    item = {'Id': metadata['image_id'], 'Architecture': 'arm64',
            'Config': {'Labels': {'io.d1env.source': metadata['source']}}}
    if mutation == 'wrong_id':
        item['Id'] = 'sha256:' + '0' * 64
    if mutation == 'wrong_arch':
        item['Architecture'] = 'amd64'
    if mutation == 'wrong_source':
        item['Config']['Labels']['io.d1env.source'] = 'untrusted/image'
    observed = DockerCommand((), 0, 'malformed' if mutation == 'malformed' else json.dumps([item]), '',
                             timed_out=mutation == 'timeout')
    monkeypatch.setattr('d1env.docker.client.DockerClient.run', lambda *args, **kw: observed)
    assert (service._runtime_image_probe()['artifact_ready'] is True) == (mutation == 'matching')


def test_service_reuses_exact_image_without_importing_or_installing(service, monkeypatch):
    expected = {'artifact_ready': True, 'image_id': 'sha256:' + 'a' * 64}
    monkeypatch.setattr(service, '_runtime_image_probe', lambda: expected)
    def forbidden(*args, **kwargs):
        raise AssertionError('existing image must not be imported')
    monkeypatch.setattr(service, 'import_ros_image', forbidden)
    assert service._prepare_runtime_image() == {**expected, 'status': 'reused'}


def test_service_unknown_image_never_attempts_import(service, monkeypatch):
    monkeypatch.setattr(service, '_runtime_image_probe', lambda: {'artifact_ready': None})
    with pytest.raises(ValueError, match='RUNTIME_IMAGE_UNKNOWN'):
        service._prepare_runtime_image()


def test_automatic_import_receives_task_cancellation_predicate(service, monkeypatch, tmp_path):
    predicate = lambda: True
    received = []
    def import_bundle(self, path, is_cancelled=lambda: False):
        received.append(is_cancelled)
        assert is_cancelled() is True
        return {'status': 'cancelled-fixture'}
    monkeypatch.setattr('d1env.docker.offline.ROSImageImporter.import_bundle', import_bundle)
    service.import_ros_image(tmp_path / 'fixed-bundle.tar', is_cancelled=predicate)
    assert received == [predicate]
