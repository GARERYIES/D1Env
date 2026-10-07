from pathlib import Path

import pytest

from d1env.models import HostFacts, utcnow

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def explicit_fake_process_entry(request, monkeypatch):
    # Subprocess-boundary tests intentionally use fixture CLIs/Processes.
    # Never let the machine's newly verified Desktop entry replace those fakes.
    if request.node.path.name in {"test_process.py", "test_docker_executor.py"}:
        from d1env.docker.endpoint import LocalDockerEndpoint
        endpoint = LocalDockerEndpoint(("docker", "--context", "default"), None, True)
        monkeypatch.setattr("d1env.docker.client.resolve_endpoint", lambda: endpoint)
        monkeypatch.setattr("d1env.process.resolve_endpoint", lambda: endpoint)


@pytest.fixture
def service(tmp_path, monkeypatch):
    from d1env.service import ApplicationService
    facts = HostFacts(os_name="Darwin", os_version="26", architecture="aarch64",
                      docker_available=False, docker_accessible=False, compose_available=False,
                      disk_free_bytes=1024**3, gpu_available=None, checked_at=utcnow())
    monkeypatch.setattr("d1env.service.inspect_host", lambda target,runner: facts)
    return ApplicationService(ROOT, tmp_path)


@pytest.fixture
def web_client(service):
    from fastapi.testclient import TestClient

    from d1env.web.app import create_app
    app = create_app(service, bootstrap_token="private-test-bootstrap")
    with TestClient(app,base_url="http://127.0.0.1:8765") as client:
        yield client


@pytest.fixture
def authenticated(web_client):
    response = web_client.post("/api/session/bootstrap", json={"token":"private-test-bootstrap"},
                               headers={"Origin":"http://127.0.0.1:8765"})
    assert response.status_code == 200
    headers = {"Origin":"http://127.0.0.1:8765", "X-CSRF-Token": response.json()["csrf_token"]}
    return web_client,headers
