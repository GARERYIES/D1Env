import importlib
import json
import os
import stat
from pathlib import Path

import pytest


def _assets(root: Path) -> Path:
    (root / "frontend/dist/assets").mkdir(parents=True)
    (root / "frontend/dist/index.html").write_text("<h1>MOCK</h1>")
    (root / "profiles").mkdir()
    (root / "profiles/demo.yaml").write_text("profile_id: demo\n")
    (root / "docs/research").mkdir(parents=True)
    (root / "docs/research/UPSTREAM_LOCK.json").write_text(json.dumps({"scope": "static"}))
    return root


def _runtime():
    return importlib.import_module("d1env.runtime")


def test_readonly_source_assets_use_private_user_state(tmp_path, monkeypatch):
    source = _assets(tmp_path / "source")
    source.chmod(0o555)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    paths = _runtime().resolve_runtime_paths(source_root=source, environ={})
    assert paths.assets_dir == source
    assert paths.state_dir.is_relative_to(home)
    assert not paths.state_dir.is_relative_to(source)
    assert stat.S_IMODE(paths.state_dir.stat().st_mode) == 0o700
    (paths.state_dir / "write-proof").write_text("owned state")
    assert not (source / "work").exists()


def test_explicit_development_state_override_is_preserved(tmp_path):
    source = _assets(tmp_path / "source")
    state = tmp_path / "开发 状态"
    paths = _runtime().resolve_runtime_paths(
        source_root=source, environ={"D1ENV_STATE_DIR": str(state)}
    )
    assert paths.state_dir == state
    assert paths.assets_dir == source


def test_frozen_assets_work_without_a_source_checkout(tmp_path, monkeypatch):
    frozen = tmp_path / "frozen"
    bundle = _assets(frozen / "assets")
    state = tmp_path / "state"
    monkeypatch.setattr("sys._MEIPASS", str(frozen), raising=False)
    paths = _runtime().resolve_runtime_paths(environ={"D1ENV_STATE_DIR": str(state)})
    assert paths.assets_dir == bundle
    assert paths.state_dir == state


@pytest.mark.parametrize("problem", ["symlink", "world_writable", "owner_mismatch"])
def test_unsafe_state_is_rejected_before_writing(tmp_path, monkeypatch, problem):
    source = _assets(tmp_path / "source")
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    state = target
    if problem == "symlink":
        state = tmp_path / "state-link"
        state.symlink_to(target, target_is_directory=True)
    elif problem == "world_writable":
        state.chmod(0o777)
    else:
        monkeypatch.setattr(os, "getuid", lambda: target.stat().st_uid + 1)
    with pytest.raises(ValueError, match="STATE"):
        if problem == "owner_mismatch":
            _runtime().ensure_private_state_dir(state)
        else:
            _runtime().resolve_runtime_paths(
                source_root=source, environ={"D1ENV_STATE_DIR": str(state)}
            )
    assert list(target.iterdir()) == []


def test_symlink_ancestor_and_incomplete_assets_are_rejected(tmp_path):
    source = _assets(tmp_path / "source")
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="STATE"):
        _runtime().resolve_runtime_paths(
            source_root=source, environ={"D1ENV_STATE_DIR": str(link / "state")}
        )
    (source / "frontend/dist/index.html").unlink()
    with pytest.raises(ValueError, match="ASSETS"):
        _runtime().resolve_runtime_paths(
            source_root=source, environ={"D1ENV_STATE_DIR": str(tmp_path / "safe")}
        )
    assert not (tmp_path / "safe").exists()


def test_explicit_asset_bundle_rejects_linked_content(tmp_path):
    source = _assets(tmp_path / "source")
    outside = tmp_path / "outside-secret"
    outside.write_text("not an asset")
    (source / "frontend/dist/assets/external.js").symlink_to(outside)
    with pytest.raises(ValueError, match="ASSETS"):
        _runtime().resolve_runtime_paths(environ={
            "D1ENV_ASSETS_DIR": str(source), "D1ENV_STATE_DIR": str(tmp_path / "state")
        })
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("asset", ["frontend/dist/assets/script.js", "profiles/demo.yaml", "docs/build/ROS_PROBE_OFFLINE.json"])
def test_group_writable_trusted_assets_are_rejected(tmp_path, asset):
    source = _assets(tmp_path / "source")
    path = source / asset
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("data only")
    path.chmod(0o664)
    with pytest.raises(ValueError, match="ASSETS_INVALID"):
        _runtime().validate_assets_dir(source)


def test_build_script_creates_reproducible_no_node_asset_bundles(tmp_path):
    import hashlib
    import subprocess
    import sys
    import zipfile
    source = _assets(tmp_path / "source")
    script = Path(__file__).resolve().parents[1] / "scripts/build-release.py"
    digests = []
    for filename in ("first.zip", "second.zip"):
        output = tmp_path / filename
        result = subprocess.run([
            sys.executable, str(script), "--source-root", str(source), "--output", str(output),
        ], capture_output=True, text=True, env={**os.environ, "PATH": ""}, timeout=10, check=False)
        assert result.returncode == 0, result.stderr
        metadata = json.loads(result.stdout)
        assert metadata["kind"] == "d1env_data_bundle"
        assert metadata["self_contained_runtime"] is False
        assert metadata["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
        with zipfile.ZipFile(output) as archive:
            assert "payload/frontend/dist/index.html" in archive.namelist()
            assert "payload/profiles/demo.yaml" in archive.namelist()
            assert "payload/docs/research/UPSTREAM_LOCK.json" in archive.namelist()
            assert all("node_modules" not in name for name in archive.namelist())
        digests.append(metadata["sha256"])
    assert digests[0] == digests[1]
    previous = (tmp_path / "first.zip").read_bytes()
    result = subprocess.run([
        sys.executable, str(script), "--source-root", str(source),
        "--output", str(tmp_path / "first.zip"),
    ], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert (tmp_path / "first.zip").read_bytes() == previous


def test_world_writable_asset_root_is_rejected(tmp_path):
    source = _assets(tmp_path / "source")
    source.chmod(0o777)
    with pytest.raises(ValueError, match="ASSETS"):
        _runtime().resolve_runtime_paths(source_root=source,
            environ={"D1ENV_STATE_DIR": str(tmp_path / "state")})


def test_group_writable_state_is_rejected(tmp_path):
    source = _assets(tmp_path / "source")
    state = tmp_path / "state"
    state.mkdir(mode=0o770)
    state.chmod(0o770)  # mkdir is filtered by the process umask.
    with pytest.raises(ValueError, match="STATE"):
        _runtime().resolve_runtime_paths(source_root=source,
            environ={"D1ENV_STATE_DIR": str(state)})
