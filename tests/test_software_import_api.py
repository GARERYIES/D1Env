import json

import pytest


def test_import_is_disabled_without_trusted_release_metadata(authenticated, service, tmp_path):
    client, _headers = authenticated
    service.root_dir = tmp_path
    result = client.get("/api/artifacts/ros-probe")
    assert result.status_code == 200
    assert result.json()["trusted_bundle"] is None
    assert result.json()["blocked_reason"]


def test_release_metadata_must_match_the_installed_software_profile(service, tmp_path):
    from test_software_plans import software_catalog
    service.catalog = software_catalog()
    service.root_dir = tmp_path
    build = tmp_path / "docs/build"
    build.mkdir(parents=True)
    lock = {"schema_version": 1, "filename": "ros-image.tar", "sha256": "b"*64,
            "size_bytes": 4, "source": "d1env/ros-probe", "image_id": "sha256:" + "a"*64,
            "architecture": "aarch64"}
    (build / "ROS_PROBE_OFFLINE.json").write_text(json.dumps(lock))
    assert service.ros_image_metadata()["trusted_bundle"]["size_bytes"] == 4
    lock["image_id"] = "sha256:" + "c"*64
    (build / "ROS_PROBE_OFFLINE.json").write_text(json.dumps(lock))
    assert service.ros_image_metadata()["trusted_bundle"] is None


def test_import_raw_upload_requires_auth_and_csrf_and_never_accepts_client_expectations(authenticated, service, monkeypatch):
    client, headers = authenticated
    monkeypatch.setattr(service, "ros_image_metadata", lambda: {
        "trusted_bundle": {"size_bytes": 4, "sha256": "a"*64}, "blocked_reason": None})
    captured = []
    def importer(path):
        captured.append(path.read_bytes())
        assert path.stat().st_mode & 0o777 == 0o600
        return {"status": "imported", "software_scope_only": True}
    monkeypatch.setattr(service, "import_ros_image", importer)
    url = "/api/artifacts/ros-probe/import"
    assert client.post(url, content=b"DATA").status_code == 403
    result = client.post(url, content=b"DATA", headers={**headers, "Content-Type": "application/octet-stream"})
    assert result.status_code == 200 and result.json()["software_scope_only"] is True
    assert captured == [b"DATA"]
    assert not list((service.store.path.parent / "uploads").glob("*"))
    assert client.post(url, content=b"DATA", headers={**headers, "Origin": "https://foreign.invalid"}).status_code == 403
    assert client.post(url, content=b"LONGER", headers={**headers, "Content-Type": "application/octet-stream"}).status_code == 413
    assert client.post(url, json={"expected_sha256": "a"*64}, headers=headers).status_code in {413, 415}
    assert captured == [b"DATA"]


def test_generic_chunked_json_body_is_bounded_before_parsing(authenticated):
    client, headers = authenticated
    def body():
        for _ in range(20):
            yield b"x" * 4096
    assert client.post("/api/plans", content=body(), headers=headers).status_code == 413


@pytest.mark.parametrize("payload", [b"", b"abc"])
def test_import_size_mismatch_is_rejected_and_staging_cleaned(authenticated, service, monkeypatch, payload):
    client, headers = authenticated
    monkeypatch.setattr(service, "ros_image_metadata", lambda: {
        "trusted_bundle": {"size_bytes": 4}, "blocked_reason": None})
    calls = []
    monkeypatch.setattr(service, "import_ros_image", lambda path: calls.append(path))
    result = client.post("/api/artifacts/ros-probe/import", content=payload,
                        headers={**headers, "Content-Type": "application/octet-stream"})
    assert result.status_code in {409, 413}
    assert not calls
    assert not list((service.store.path.parent / "uploads").glob("*"))


def test_import_rejection_explains_the_failed_phase_and_evidence(authenticated, service, monkeypatch):
    client, headers = authenticated
    monkeypatch.setattr(service, "ros_image_metadata", lambda: {
        "trusted_bundle": {"size_bytes": 4}, "blocked_reason": None})
    def reject(path):
        raise ValueError("OFFLINE_HASH_MISMATCH: 镜像导入校验失败；检测证据：摘要不符；请重新取得完整发行工件。")
    monkeypatch.setattr(service, "import_ros_image", reject)
    response = client.post("/api/artifacts/ros-probe/import", content=b"DATA",
                           headers={**headers, "Content-Type": "application/octet-stream"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "OFFLINE_HASH_MISMATCH" and "摘要不符" in detail["message"]
    assert detail["remediation"]
