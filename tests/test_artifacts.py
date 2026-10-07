import pytest
from pydantic import ValidationError

from d1env.models import ArtifactRef, DeploymentRequest


@pytest.mark.parametrize("identifier", ["latest", "sha256:" + "0"*64, "sha256:placeholder"])
def test_unlocked_real_artifact_identifiers_rejected(identifier):
    with pytest.raises(ValidationError):
        ArtifactRef(kind="registry",source="registry.example/test",architecture="x86_64",immutable_id=identifier)


def test_remote_target_and_string_booleans_rejected():
    with pytest.raises(ValidationError):
        DeploymentRequest(target_id="ssh://remote")


# Offline bundles are data, not installers or an instruction to load Docker layers.
import hashlib
import importlib
import io
import json
import stat
import tarfile
import zipfile
from pathlib import Path


def _offline():
    return importlib.import_module("d1env.artifacts")


def _bundle(tmp_path: Path, *, format="zip", members=None, manifest=None) -> Path:
    data = [("payload/说明.txt", b"trusted data")]
    records = data if members is None else members
    if manifest is None:
        manifest = {"schema_version": 1, "kind": "d1env_data_bundle", "bundle_id": "test-data",
                    "files": [{"path": name, "size_bytes": len(content),
                               "sha256": hashlib.sha256(content).hexdigest()}
                              for name, content in records]}
    path = tmp_path / f"bundle.{format}"
    manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
    if format == "zip":
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("d1env-offline.json", manifest_bytes)
            for name, content in records:
                archive.writestr(name, content)
    else:
        with tarfile.open(path, "w") as archive:
            for name, content in [("d1env-offline.json", manifest_bytes), *records]:
                item = tarfile.TarInfo(name)
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("format", ["zip", "tar"])
def test_trusted_data_bundle_validates_without_writes_then_imports(tmp_path, format):
    archive = _bundle(tmp_path, format=format)
    destination = tmp_path / "imported"
    validated = _offline().validate_offline_archive(archive, _digest(archive), destination)
    assert validated.bundle_id == "test-data"
    assert validated.total_bytes == 12
    assert not destination.exists()
    imported = _offline().import_offline_archive(archive, _digest(archive), destination)
    assert imported.destination == destination
    assert (destination / "payload/说明.txt").read_bytes() == b"trusted data"
    assert stat.S_IMODE((destination / "payload/说明.txt").stat().st_mode) == 0o600


@pytest.mark.parametrize("bad_hash", [None, "", "0" * 64, "sha256:placeholder", "f" * 64])
def test_trusted_expected_digest_is_mandatory_and_checked(tmp_path, bad_hash):
    archive = _bundle(tmp_path)
    destination = tmp_path / "never-created"
    with pytest.raises(ValueError, match="DIGEST"):
        _offline().import_offline_archive(archive, bad_hash, destination)
    assert not destination.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "payload/../../escape", "C:/escape", "payload\\escape"])
@pytest.mark.parametrize("format", ["zip", "tar"])
def test_archive_path_escape_is_rejected_before_writing(tmp_path, name, format):
    archive = _bundle(tmp_path, format=format, members=[(name, b"not trusted")])
    destination = tmp_path / "never-created"
    with pytest.raises(ValueError, match="PATH"):
        _offline().import_offline_archive(archive, _digest(archive), destination)
    assert not destination.exists()


@pytest.mark.parametrize("format", ["zip", "tar"])
def test_duplicate_members_and_case_collision_are_rejected(tmp_path, format):
    archive = _bundle(tmp_path, format=format,
                      members=[("payload/readme", b"a"), ("payload/README", b"b")])
    with pytest.raises(ValueError, match="DUPLICATE"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")


@pytest.mark.parametrize("link_type", ["symlink", "hardlink"])
def test_tar_links_are_rejected(tmp_path, link_type):
    archive = _bundle(tmp_path, format="tar")
    with tarfile.open(archive, "a") as tar:
        item = tarfile.TarInfo("payload/link")
        item.type = tarfile.SYMTYPE if link_type == "symlink" else tarfile.LNKTYPE
        item.linkname = "../../outside"
        tar.addfile(item)
    with pytest.raises(ValueError, match="TYPE"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")


def test_zip_symlink_is_rejected(tmp_path):
    archive = _bundle(tmp_path)
    with zipfile.ZipFile(archive, "a") as zipped:
        item = zipfile.ZipInfo("payload/link")
        item.create_system = 3
        item.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(item, "../../outside")
    with pytest.raises(ValueError, match="TYPE"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")


def test_capacity_and_payload_hash_fail_without_partial_files(tmp_path):
    archive = _bundle(tmp_path)
    destination = tmp_path / "out"
    with pytest.raises(ValueError, match="CAPACITY"):
        _offline().import_offline_archive(archive, _digest(archive), destination, max_total_bytes=8)
    assert not destination.exists()
    manifest = {"schema_version": 1, "kind": "d1env_data_bundle", "bundle_id": "test-data",
                "files": [{"path": "payload/说明.txt", "size_bytes": 12, "sha256": "a" * 64}]}
    archive = _bundle(tmp_path, manifest=manifest)
    with pytest.raises(ValueError, match="PAYLOAD"):
        _offline().import_offline_archive(archive, _digest(archive), destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".d1env-import-*"))


def test_existing_user_destination_and_repeat_import_are_preserved(tmp_path):
    archive = _bundle(tmp_path)
    destination = tmp_path / "user-data"
    destination.mkdir()
    (destination / "map.yaml").write_text("keep me")
    with pytest.raises(ValueError, match="DESTINATION"):
        _offline().import_offline_archive(archive, _digest(archive), destination)
    assert (destination / "map.yaml").read_text() == "keep me"
    imported = tmp_path / "new-data"
    _offline().import_offline_archive(archive, _digest(archive), imported)
    with pytest.raises(ValueError, match="DESTINATION"):
        _offline().import_offline_archive(archive, _digest(archive), imported)
    assert (imported / "payload/说明.txt").read_bytes() == b"trusted data"


def test_embedded_script_is_only_imported_as_non_executable_data(tmp_path):
    marker = tmp_path / "script-ran"
    script = f"#!/bin/sh\ntouch '{marker}'\n".encode()
    archive = _bundle(tmp_path, members=[("payload/install.sh", script)])
    destination = tmp_path / "out"
    _offline().import_offline_archive(archive, _digest(archive), destination)
    assert not marker.exists()
    assert (destination / "payload/install.sh").read_bytes() == script
    assert not (destination / "payload/install.sh").stat().st_mode & 0o111


def test_arbitrary_docker_save_or_unknown_manifest_is_not_extracted(tmp_path):
    manifest = {"schema_version": 1, "kind": "docker_image_archive", "bundle_id": "test-data",
                "files": []}
    archive = _bundle(tmp_path, manifest=manifest)
    with pytest.raises(ValueError, match="MANIFEST"):
        _offline().import_offline_archive(archive, _digest(archive), tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_huge_tar_member_is_rejected_before_skipping_or_decompressing(tmp_path):
    archive = tmp_path / "huge.tar"
    with tarfile.open(archive, "w") as tar:
        item = tarfile.TarInfo("payload/huge.bin")
        item.size = 2 ** 40
        tar.addfile(item)
    with pytest.raises(ValueError, match="CAPACITY"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_fifo_input_is_rejected_without_waiting_for_a_writer(tmp_path):
    import os
    import signal
    archive = tmp_path / "pipe.tar"
    os.mkfifo(archive)
    previous = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("blocked FIFO")))
    signal.alarm(1)
    try:
        with pytest.raises(ValueError, match="TYPE"):
            _offline().validate_offline_archive(archive, "a" * 64, tmp_path / "out")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_failed_publish_leaves_no_partial_import_and_preserves_a_racing_directory(tmp_path, monkeypatch):
    import os
    archive = _bundle(tmp_path)
    destination = tmp_path / "out"
    original = _offline()._publish_no_replace

    def race(source, target):
        os.mkdir(target)
        (target / "user-map.yaml").write_text("preserve")
        return original(source, target)

    monkeypatch.setattr(_offline(), "_publish_no_replace", race)
    with pytest.raises(ValueError, match="DESTINATION"):
        _offline().import_offline_archive(archive, _digest(archive), destination)
    assert list(destination.iterdir()) == [destination / "user-map.yaml"]
    assert (destination / "user-map.yaml").read_text() == "preserve"
    assert not list(tmp_path.glob(".d1env-import-*"))


def test_unicode_filename_collision_is_rejected(tmp_path):
    archive = _bundle(tmp_path, members=[("payload/é.txt", b"a"), ("payload/e\u0301.txt", b"b")])
    with pytest.raises(ValueError, match="DUPLICATE"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")


def test_case_insensitive_file_parent_conflict_is_rejected(tmp_path):
    archive = _bundle(tmp_path, members=[("payload/FILE", b"a"), ("payload/file/child", b"b")])
    with pytest.raises(ValueError, match="PATH"):
        _offline().validate_offline_archive(archive, _digest(archive), tmp_path / "out")
