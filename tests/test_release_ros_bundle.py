"""Pure-file checks for the optional trusted ROS payload; no Docker calls."""

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from d1env.runtime import resolve_runtime_paths, validate_assets_dir

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build-release.py"
FILENAME = "d1env-ros-probe-m3-aarch64.tar"
PAYLOAD = b"MOCK ROS bundle fixture; not a real image"


@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location("d1env_release_ros_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs(tmp_path):
    assets = tmp_path / "installed-assets"
    (assets / "frontend/dist").mkdir(parents=True)
    (assets / "frontend/dist/index.html").write_text("<h1>MOCK</h1>")
    (assets / "profiles").mkdir()
    (assets / "profiles/demo.yaml").write_text("profile_id: demo\n")
    (assets / "docs/research").mkdir(parents=True)
    (assets / "docs/research/UPSTREAM_LOCK.json").write_text("{}")
    (assets / "docs/build").mkdir()
    lock = {"schema_version": 1, "filename": FILENAME,
            "sha256": hashlib.sha256(PAYLOAD).hexdigest(), "size_bytes": len(PAYLOAD),
            "source": "d1env/ros-probe", "image_id": "sha256:" + "5" * 64,
            "architecture": "aarch64"}
    (assets / "docs/build/ROS_PROBE_OFFLINE.json").write_text(json.dumps(lock))
    source = tmp_path / "provided.tar"
    source.write_bytes(PAYLOAD)
    return assets, source, lock


def test_matching_ros_payload_is_copied_under_the_installed_lock_filename(builder, tmp_path):
    assets, source, lock = _inputs(tmp_path)
    metadata = builder.copy_ros_bundle(source, assets, "aarch64")
    copied = assets / "bundles" / FILENAME
    assert copied.read_bytes() == PAYLOAD
    assert source.read_bytes() == PAYLOAD
    assert stat.S_IMODE(copied.stat().st_mode) == 0o644
    assert metadata["filename"] == FILENAME
    assert metadata["sha256"] == lock["sha256"]
    assert metadata["size_bytes"] == len(PAYLOAD)
    assert metadata["image_id"] == "sha256:" + "5" * 64
    assert validate_assets_dir(assets) == assets
    assert not any(path.suffix == ".dmg" for path in assets.rglob("*"))


@pytest.mark.parametrize("problem", ["digest", "size", "architecture", "source", "filename", "image_id"])
def test_ros_payload_rejects_wrong_lock_or_bytes_before_creating_assets(builder, tmp_path, problem):
    assets, source, lock = _inputs(tmp_path)
    if problem == "digest":
        source.write_bytes(PAYLOAD.replace(b"MOCK", b"FAKE"))
    elif problem == "size":
        source.write_bytes(PAYLOAD[:-1])
    elif problem == "architecture":
        lock["architecture"] = "x86_64"
    elif problem == "source":
        lock["source"] = "arbitrary/not-ros"
    elif problem == "filename":
        lock["filename"] = "../outside.tar"
    else:
        lock["image_id"] = "sha256:" + "0" * 64
    (assets / "docs/build/ROS_PROBE_OFFLINE.json").write_text(json.dumps(lock))
    with pytest.raises(ValueError, match="ROS_BUNDLE"):
        builder.copy_ros_bundle(source, assets, "aarch64")
    assert not (assets / "bundles").exists()
    assert not (tmp_path / "outside.tar").exists()


@pytest.mark.parametrize("problem", ["symlink", "hardlink", "group_writable", "fifo"])
def test_ros_payload_rejects_untrusted_input_files(builder, tmp_path, problem):
    assets, source, _ = _inputs(tmp_path)
    if problem == "symlink":
        linked = tmp_path / "input-link.tar"
        linked.symlink_to(source)
        source = linked
    elif problem == "hardlink":
        os.link(source, tmp_path / "second-input-name")
    elif problem == "group_writable":
        source.chmod(0o664)
    else:
        source.unlink()
        os.mkfifo(source)
    with pytest.raises(ValueError, match="ROS_BUNDLE"):
        builder.copy_ros_bundle(source, assets, "aarch64")
    assert not (assets / "bundles").exists()


@pytest.mark.parametrize("problem", ["file", "link"])
def test_ros_payload_does_not_replace_a_previous_destination(builder, tmp_path, problem):
    assets, source, _ = _inputs(tmp_path)
    bundles = assets / "bundles"
    bundles.mkdir()
    existing = bundles / FILENAME
    outside = tmp_path / "unrelated-user-data"
    outside.write_bytes(b"preserved")
    if problem == "file":
        existing.write_bytes(b"previous release data")
    else:
        existing.symlink_to(outside)
    with pytest.raises(ValueError, match="ROS_BUNDLE"):
        builder.copy_ros_bundle(source, assets, "aarch64")
    assert outside.read_bytes() == b"preserved"
    assert existing.is_symlink() if problem == "link" else existing.read_bytes() == b"previous release data"


def test_ros_bundle_argument_cannot_be_ignored_by_the_assets_only_command(tmp_path):
    assets, source, _ = _inputs(tmp_path)
    output = tmp_path / "never.zip"
    result = subprocess.run([sys.executable, str(SCRIPT), "--source-root", str(assets),
        "--ros-bundle", str(source), "--output", str(output)],
        capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert "ROS_BUNDLE_PORTABLE_ONLY" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("problem", ["directory_link", "file_link", "group_writable", "special"])
def test_runtime_rejects_untrusted_bundled_payload_assets_before_state_creation(tmp_path, problem):
    assets, _, _ = _inputs(tmp_path)
    bundles = assets / "bundles"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data").write_bytes(b"preserved")
    if problem == "directory_link":
        bundles.symlink_to(outside, target_is_directory=True)
    else:
        bundles.mkdir()
        entry = bundles / FILENAME
        if problem == "file_link":
            entry.symlink_to(outside / "data")
        elif problem == "group_writable":
            entry.write_bytes(PAYLOAD)
            entry.chmod(0o664)
        else:
            os.mkfifo(entry)
    with pytest.raises(ValueError, match="ASSETS_INVALID"):
        resolve_runtime_paths(source_root=assets, environ={"D1ENV_STATE_DIR": str(tmp_path / "never-state")})
    assert (outside / "data").read_bytes() == b"preserved"
    assert not (tmp_path / "never-state").exists()
