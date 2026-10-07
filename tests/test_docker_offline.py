"""Offline import unit fixtures; no daemon or executable archives involved."""

import fcntl
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from d1env.docker.client import DockerClient, DockerCommand
from d1env.docker.offline import ROSImageImporter
from d1env.models import ArtifactRef


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def tar_bytes(files, malicious=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, data in files:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if malicious:
            name, kind = malicious
            member = tarfile.TarInfo(name)
            if kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = "/tmp/outside"
            elif kind == "hardlink":
                member.type = tarfile.LNKTYPE
                member.linkname = "/tmp/outside"
            else:
                member.size = 1
            archive.addfile(member, io.BytesIO(b"x") if member.isfile() else None)
    return output.getvalue()


def image_tar(*, repotags=None, malicious=None, source="d1env/ros-probe", architecture="arm64"):
    layer = gzip.compress(tar_bytes([("test.txt", b"image data; never run")]))
    config = json.dumps(
        {
            "architecture": architecture,
            "os": "linux",
            "config": {
                "Labels": {"io.d1env.source": source},
                "User": "10001:10001",
                "Entrypoint": ["/opt/d1env/entrypoint.sh"],
                "Cmd": ["idle"],
            },
        }
    ).encode()
    config_digest, layer_digest = digest(config), digest(layer)
    manifest = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": "sha256:" + config_digest,
                "size": len(config),
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                    "digest": "sha256:" + layer_digest,
                    "size": len(layer),
                }
            ],
        }
    ).encode()
    manifest_digest = digest(manifest)
    index = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": "sha256:" + manifest_digest,
                    "size": len(manifest),
                    "platform": {"os": "linux", "architecture": "arm64"},
                }
            ],
        }
    ).encode()
    image_id = "sha256:" + digest(index)
    top_index = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.index.v1+json",
                    "digest": image_id,
                    "size": len(index),
                }
            ],
        }
    ).encode()
    docker_manifest = json.dumps(
        [
            {
                "Config": f"blobs/sha256/{config_digest}",
                "RepoTags": repotags,
                "Layers": [f"blobs/sha256/{layer_digest}"],
            }
        ]
    ).encode()
    files = [
        ("index.json", top_index),
        ("oci-layout", b'{"imageLayoutVersion":"1.0.0"}'),
        ("manifest.json", docker_manifest),
        (f"blobs/sha256/{image_id[7:]}", index),
        (f"blobs/sha256/{manifest_digest}", manifest),
        (f"blobs/sha256/{config_digest}", config),
        (f"blobs/sha256/{layer_digest}", layer),
    ]
    return tar_bytes(files, malicious), image_id


def bundle(
    tmp_path,
    *,
    image=None,
    identity=None,
    manifest_changes=None,
    outer_malicious=None,
    image_kwargs=None,
):
    if image is None:
        image, identity = image_tar(**(image_kwargs or {}))
    ros_manifest = {
        "schema_version": 1,
        "kind": "d1env_ros_image",
        "source": "d1env/ros-probe",
        "architecture": "aarch64",
        "image_id": identity,
        "image_archive": {
            "path": "payload/image.tar",
            "sha256": digest(image),
            "size_bytes": len(image),
        },
    }
    ros_manifest.update(manifest_changes or {})
    payload = json.dumps(ros_manifest).encode()
    outer = {
        "schema_version": 1,
        "kind": "d1env_data_bundle",
        "bundle_id": "ros-probe-aarch64",
        "files": [
            {
                "path": "payload/ros-image.json",
                "sha256": digest(payload),
                "size_bytes": len(payload),
            },
            {"path": "payload/image.tar", "sha256": digest(image), "size_bytes": len(image)},
        ],
    }
    raw = tar_bytes(
        [
            ("d1env-offline.json", json.dumps(outer).encode()),
            ("payload/ros-image.json", payload),
            ("payload/image.tar", image),
        ],
        outer_malicious,
    )
    path = tmp_path / "ros-image-bundle.tar"
    path.write_bytes(raw)
    expected = ArtifactRef(
        kind="local_build", source="d1env/ros-probe", architecture="aarch64", immutable_id=identity
    )
    return path, digest(raw), expected


class ImportClient:
    def __init__(self, artifact):
        self.artifact = artifact
        self.present = False
        self.calls = []
        self.bad_identity = False
        self.on_load = None

    def run(self, args, timeout_s=5.0, is_cancelled=lambda: False):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            if not self.present:
                return DockerCommand(args, 1, "", "No such image")
            payload = {
                "Id": self.artifact.immutable_id if not self.bad_identity else "sha256:" + "f" * 64,
                "Architecture": "arm64",
                "Os": "linux",
                "Config": {"Labels": {"io.d1env.source": "d1env/ros-probe"}},
            }
            return DockerCommand(args, 0, json.dumps([payload]), "")
        if args[:2] == ("load", "--input"):
            path = Path(args[2])
            assert path.is_file() and not path.is_symlink()
            assert path.name == "image.tar" and path.parent.name == "payload"
            if self.on_load:
                self.on_load(path)
            self.present = True
            return DockerCommand(args, 0, "Loaded image ID: " + self.artifact.immutable_id, "")
        raise AssertionError(args)


def importer(tmp_path, expected, trusted, client, **limits):
    return ROSImageImporter(expected, trusted, tmp_path / "state", client=client, **limits)


def test_trusted_bundle_loads_only_private_copy_verifies_identity_and_reuses_image(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)
    runner = importer(tmp_path, expected, trusted, client)
    first = runner.import_bundle(path)
    assert first["status"] == "imported" and first["software_scope_only"] is True
    assert first["image_id"] == expected.immutable_id and first["architecture"] == "aarch64"
    load_path = Path(next(args[2] for args in client.calls if args[0] == "load"))
    assert load_path != path and not load_path.exists()
    repeated = runner.import_bundle(path)
    assert repeated["status"] == "reused"
    assert len([args for args in client.calls if args[0] == "load"]) == 1
    assert not any("rm" in args or "import" in args for args in client.calls)


@pytest.mark.parametrize(
    "mutation", ["wrong_hash", "wrong_source", "wrong_arch", "wrong_id", "extra_manifest_field"]
)
def test_untrusted_or_mismatched_bundle_never_touches_daemon(tmp_path, mutation):
    changes = {
        "wrong_source": {"source": "user/evil"},
        "wrong_arch": {"architecture": "x86_64"},
        "wrong_id": {"image_id": "sha256:" + "f" * 64},
        "extra_manifest_field": {"script": "touch /tmp/pwn"},
    }
    path, trusted, expected = bundle(tmp_path, manifest_changes=changes.get(mutation))
    client = ImportClient(expected)
    with pytest.raises(ValueError):
        importer(
            tmp_path, expected, "f" * 64 if mutation == "wrong_hash" else trusted, client
        ).import_bundle(path)
    assert client.calls == []


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "file"])
@pytest.mark.parametrize("place", ["outer", "inner"])
def test_unsafe_paths_links_and_duplicate_members_are_rejected_before_load(tmp_path, kind, place):
    malicious = ("payload/image.tar" if kind == "file" else "../escape", kind)
    if place == "inner":
        image, identity = image_tar(
            malicious=("index.json" if kind == "file" else "../escape", kind)
        )
        path, trusted, expected = bundle(tmp_path, image=image, identity=identity)
    else:
        path, trusted, expected = bundle(tmp_path, outer_malicious=malicious)
    client = ImportClient(expected)
    with pytest.raises(ValueError):
        importer(tmp_path, expected, trusted, client).import_bundle(path)
    assert client.calls == []


def test_extra_docker_tags_cannot_overwrite_user_images(tmp_path):
    path, trusted, expected = bundle(tmp_path, image_kwargs={"repotags": ["user/image:latest"]})
    client = ImportClient(expected)
    with pytest.raises(ValueError):
        importer(tmp_path, expected, trusted, client).import_bundle(path)
    assert client.calls == []


@pytest.mark.parametrize("limit", ["max_archive_bytes", "max_unpacked_bytes"])
def test_capacity_limits_reject_before_daemon_and_preserve_input(tmp_path, limit):
    path, trusted, expected = bundle(tmp_path)
    before = path.read_bytes()
    client = ImportClient(expected)
    with pytest.raises(ValueError):
        importer(tmp_path, expected, trusted, client, **{limit: 100}).import_bundle(path)
    assert client.calls == [] and path.read_bytes() == before


def test_load_post_inspect_mismatch_is_failure_without_image_deletion(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)
    client.bad_identity = True
    with pytest.raises(ValueError):
        importer(tmp_path, expected, trusted, client).import_bundle(path)
    assert len([args for args in client.calls if args[0] == "load"]) == 1
    assert not any("rm" in args for args in client.calls)


def test_active_job_lock_blocks_import_and_cancel_is_explicit(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)
    runner = importer(tmp_path, expected, trusted, client)
    lock_path = tmp_path / "state" / "locks" / "local.lock"
    lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="IMPORT_TARGET_BUSY"):
            runner.import_bundle(path)
    with pytest.raises(ValueError, match="IMPORT_CANCELLED"):
        runner.import_bundle(path, is_cancelled=lambda: True)
    assert client.calls == []


def test_mutating_original_after_validation_cannot_replace_loaded_private_copy(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)

    def mutate_original(staged):
        path.write_bytes(b"untrusted replacement")
        assert staged.read_bytes() != path.read_bytes()

    client.on_load = mutate_original
    result = importer(tmp_path, expected, trusted, client).import_bundle(path)
    assert result["status"] == "imported"


def test_docker_client_only_loads_fixed_private_image_tar_path(tmp_path):
    with pytest.raises(ValueError):
        DockerClient().run(("load", "--input", "/tmp/user-image.tar"))
    with pytest.raises(ValueError):
        DockerClient().run(("import", "/tmp/image.tar"))


def test_load_failure_is_a_user_visible_value_error_without_image_removal(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)
    original = client.run

    def fail_load(args, timeout_s=5.0, is_cancelled=lambda: False):
        if args[0] == "load":
            return DockerCommand(args, 1, "", "permission denied")
        return original(args, timeout_s=timeout_s, is_cancelled=is_cancelled)

    client.run = fail_load
    with pytest.raises(ValueError, match="permission denied"):
        importer(tmp_path, expected, trusted, client).import_bundle(path)
    assert not any("rm" in args for args in client.calls)


def test_unowned_existing_receipt_is_not_overwritten(tmp_path):
    path, trusted, expected = bundle(tmp_path)
    client = ImportClient(expected)
    runner = importer(tmp_path, expected, trusted, client)
    receipts = tmp_path / "state" / "offline-imports"
    receipts.mkdir()
    receipt = receipts / f"{trusted}.json"
    receipt.write_text('{"user_data":"keep"}')
    with pytest.raises(ValueError, match="IMPORT_RECEIPT_INVALID"):
        runner.import_bundle(path)
    assert receipt.read_text() == '{"user_data":"keep"}'
    assert not any(args[0] == "load" for args in client.calls)
