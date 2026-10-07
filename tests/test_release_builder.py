import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build-release.py"
SOURCE_LOCK = ROOT / "docs/build/PYTHON_RUNTIME_LOCK.json"
OFFICIAL_RUNTIME = ROOT / "work/python/official-20260610/python"
OFFICIAL_ARCHIVE = ROOT / "work/python/cpython-3.10.20-20260610-official.tar.gz"


def test_portable_builder_rejects_an_executable_without_the_full_runtime(tmp_path):
    runtime = tmp_path / "not-a-runtime"
    (runtime / "bin").mkdir(parents=True)
    marker = tmp_path / "executed"
    binary = runtime / "bin/python3.10"
    binary.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    binary.chmod(0o700)
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--portable", "--runtime", str(runtime),
        "--wheel", str(tmp_path / "missing.whl"), "--requirements", str(tmp_path / "missing.txt"),
        "--output", str(tmp_path / "never.tar.gz"),
    ], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert "RUNTIME_INCOMPLETE" in result.stderr
    assert not marker.exists()
    assert not (tmp_path / "never.tar.gz").exists()


def test_real_portable_runtime_moves_and_reads_its_packaged_assets_without_dev_tools(tmp_path):
    runtime = Path(os.environ.get("D1ENV_RELEASE_RUNTIME", str(
        ROOT / "work/python/cpython-3.10.20-macos-aarch64-none")))
    wheel = Path(os.environ.get("D1ENV_RELEASE_WHEEL", str(
        ROOT / "work/m3-dist/d1env-0.2.0-py3-none-any.whl")))
    requirements = Path(os.environ.get("D1ENV_RELEASE_REQUIREMENTS", str(
        ROOT / "work/m3-runtime-requirements.txt")))
    if not all(path.exists() for path in (runtime, wheel, requirements)):
        pytest.skip("真实发行集成需完整 native CPython、实际项目 wheel 与锁定 requirements；未验证")
    if "macos" in runtime.name and sys.platform != "darwin":
        pytest.skip("现有 runtime 是 Mac 候选，不能用它伪造 Linux 发行验证")
    output = tmp_path / "candidate.tar.gz"
    native = "macos" if sys.platform == "darwin" else "linux"
    architecture = {"arm64": "aarch64", "AMD64": "x86_64"}.get(platform.machine(), platform.machine())
    built = subprocess.run([
        sys.executable, str(SCRIPT), "--portable", "--runtime", str(runtime),
        "--wheel", str(wheel), "--requirements", str(requirements),
        "--platform", native, "--architecture", architecture, "--output", str(output),
    ], env={**os.environ, "HTTPS_PROXY": "http://127.0.0.1:1",
            "HTTP_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1",
            "NO_PROXY": ""}, capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stderr
    metadata = json.loads(built.stdout)
    assert metadata["self_contained_runtime"] is True
    assert metadata["platform"] == native
    assert metadata["architecture"] == architecture
    assert metadata["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = _assert_relocated_bundle(output, metadata, wheel, tmp_path)
    assert manifest["runtime_provenance"]["status"] == "blocked"
    assert manifest["runtime_provenance"]["download_archive_sha256"] is None
    assert manifest["runtime_provenance"]["upstream_commit"] is None


def _assert_relocated_bundle(output, metadata, wheel, tmp_path):
    moved = tmp_path / "移动 后的位置"
    moved.mkdir()
    with tarfile.open(output, "r:gz") as archive:
        archive.extractall(moved, filter="data")
    bundle = moved / metadata["bundle_directory"]
    launcher = bundle / "d1env.sh"
    state = tmp_path / "independent-state"
    env = {**os.environ, "PATH": "", "D1ENV_STATE_DIR": str(state)}
    env.pop("D1ENV_ASSETS_DIR", None)
    help_result = subprocess.run([str(launcher), "--help"], cwd=moved, env=env,
                                 capture_output=True, text=True, timeout=15, check=False)
    assert help_result.returncode == 0, help_result.stderr
    assert "D1Env" in help_result.stdout
    if metadata["platform"] == "macos":
        clickable = bundle / "D1Env.command"
        assert clickable.is_file()
        clicked = subprocess.run([str(clickable), "--help"], cwd=moved, env=env,
                                 capture_output=True, text=True, timeout=15, check=False)
        assert clicked.returncode == 0, clicked.stderr
        assert "D1Env" in clicked.stdout
    python = bundle / "runtime/bin/python3.10"
    script = "from d1env.runtime import resolve_runtime_paths; import json; p=resolve_runtime_paths(); print(json.dumps({'assets':str(p.assets_dir),'state':str(p.state_dir),'html':(p.assets_dir/'frontend/dist/index.html').read_text()}))"
    result = subprocess.run([str(python), "-I", "-B", "-c", script], cwd=moved, env=env,
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert Path(resolved["assets"]).is_relative_to(bundle)
    assert Path(resolved["state"]) == state
    assert "D1Env" in resolved["html"]
    doctor = subprocess.run([str(launcher), "doctor"], cwd=moved, env=env,
                            capture_output=True, text=True, timeout=20, check=False)
    assert doctor.returncode in (0, 1), doctor.stderr
    diagnosed = json.loads(doctor.stdout)
    assert diagnosed["telemetry"]["status"] == "UNKNOWN"
    assert next(check for check in diagnosed["checks"] if check["code"] == "ROBOT")["status"] == "UNKNOWN"
    assert doctor.returncode == int(any(check["status"] == "FAIL" for check in diagnosed["checks"]))
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    server = subprocess.Popen([str(launcher), "ui", "--demo", "--no-browser", "--port", str(port)],
                              cwd=moved, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                with opener.open(base, timeout=1) as response:
                    html = response.read().decode()
                break
            except urllib.error.URLError:
                assert server.poll() is None, server.communicate(timeout=1)
                assert time.monotonic() < deadline, "便携包本地服务未启动"
                time.sleep(.05)
        assert html == resolved["html"]
        static_path = re.search(r'src="(/assets/[^"]+\.js)"', html)
        assert static_path is not None
        with opener.open(base + static_path.group(1), timeout=2) as response:
            assert len(response.read()) > 100
        with pytest.raises(urllib.error.HTTPError) as rejected:
            opener.open(base + "/api/catalog", timeout=2)
        assert rejected.value.code == 401
        request = urllib.request.Request(base, headers={"Host": "attacker.invalid"})
        with pytest.raises(urllib.error.HTTPError) as rejected:
            opener.open(request, timeout=2)
        assert rejected.value.code == 403
    finally:
        server.terminate()
        server.communicate(timeout=10)
    manifest = json.loads((bundle / "D1ENV-RELEASE.json").read_text())
    assert manifest["runtime"]["python_version"].startswith("3.10.")
    assert manifest["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert manifest["build_dependency_source"] == "hash_locked_cache"
    assert (bundle / manifest["runtime_provenance"]["local_license_path"]).is_file()
    assert manifest["signed_release"] is False
    assert any(item["path"].endswith("lib/python3.10/json/__init__.py") for item in manifest["files"])
    for item in manifest["files"]:
        if item["path"].endswith(".pth"):
            content = (bundle / item["path"]).read_text()
            assert "__editable__" not in content
            assert not any(line.startswith("/") for line in content.splitlines())
    return manifest


def test_verified_official_runtime_source_builds_a_relocated_candidate(tmp_path):
    wheel = ROOT / "work/m3-dist/d1env-0.2.0-py3-none-any.whl"
    requirements = ROOT / "work/m3-runtime-requirements.txt"
    if sys.platform != "darwin" or not all(path.exists() for path in
            (OFFICIAL_RUNTIME, OFFICIAL_ARCHIVE, SOURCE_LOCK, wheel, requirements)):
        pytest.skip("官方原生 Mac 来源工件缺失；来源/搬迁集成未验证")
    output = tmp_path / "official-candidate.tar.gz"
    built = subprocess.run([
        sys.executable, str(SCRIPT), "--portable", "--runtime", str(OFFICIAL_RUNTIME),
        "--runtime-source-archive", str(OFFICIAL_ARCHIVE), "--runtime-provenance-json", str(SOURCE_LOCK),
        "--wheel", str(wheel), "--requirements", str(requirements), "--platform", "macos",
        "--architecture", "aarch64", "--output", str(output),
    ], capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stderr
    metadata = json.loads(built.stdout)
    assert metadata["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = _assert_relocated_bundle(output, metadata, wheel, tmp_path)
    provenance = manifest["runtime_provenance"]
    assert provenance["status"] == "verified"
    assert provenance["download_archive_sha256"] == hashlib.sha256(OFFICIAL_ARCHIVE.read_bytes()).hexdigest()
    assert provenance["build_tool_commit"] == json.loads(SOURCE_LOCK.read_text())["build_tool_commit"]
    assert provenance["cpython_source_commit"] is None
    assert provenance["bundled_library_license_completeness"] == "blocked"


@pytest.mark.parametrize("changed", ["archive_hash", "archive_size", "runtime_tree"])
def test_source_provenance_rejects_modified_inputs_before_executing_runtime(tmp_path, changed):
    import shutil
    wheel = ROOT / "work/m3-dist/d1env-0.2.0-py3-none-any.whl"
    requirements = ROOT / "work/m3-runtime-requirements.txt"
    if not all(path.exists() for path in (OFFICIAL_RUNTIME, OFFICIAL_ARCHIVE, SOURCE_LOCK, wheel, requirements)):
        pytest.skip("来源锁回归需实际源归档/运行时；未验证")
    record = json.loads(SOURCE_LOCK.read_text())
    runtime = OFFICIAL_RUNTIME
    marker = tmp_path / "executed-unverified-interpreter"
    if changed == "archive_hash":
        record["download_archive_sha256"] = "1" * 64
    elif changed == "archive_size":
        record["download_archive_size_bytes"] += 1
    else:
        runtime = tmp_path / "modified-runtime"
        shutil.copytree(OFFICIAL_RUNTIME, runtime, symlinks=True)
        (runtime / "bin/python3.10").write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    provenance = tmp_path / "source.json"
    provenance.write_text(json.dumps(record))
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--portable", "--runtime", str(runtime),
        "--runtime-source-archive", str(OFFICIAL_ARCHIVE), "--runtime-provenance-json", str(provenance),
        "--wheel", str(wheel), "--requirements", str(requirements), "--output", str(tmp_path / "never.tar.gz"),
    ], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 1
    assert "RUNTIME_PROVENANCE_MISMATCH" in result.stderr
    assert not marker.exists()
    assert not (tmp_path / "never.tar.gz").exists()


def test_runtime_metadata_probe_never_executes_original_site_pth_hooks(tmp_path):
    import shutil
    runtime = ROOT / "work/python/cpython-3.10.20-macos-aarch64-none"
    wheel = ROOT / "work/m3-dist/d1env-0.2.0-py3-none-any.whl"
    requirements = ROOT / "work/m3-runtime-requirements.txt"
    if sys.platform != "darwin" or not all(path.exists() for path in (runtime, wheel, requirements)):
        pytest.skip("native 完整运行时输入缺失；不执行伪造的运行时验证")
    supplied = tmp_path / "provided-runtime"
    shutil.copytree(runtime, supplied, symlinks=True)
    marker = tmp_path / "unexpected-code-execution"
    hook = supplied / "lib/python3.10/site-packages/injected.pth"
    hook.write_text(f"import pathlib; pathlib.Path({str(marker)!r}).write_text('executed')\n")
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--portable", "--runtime", str(supplied),
        "--wheel", str(wheel), "--requirements", str(requirements), "--platform", "linux",
        "--architecture", "aarch64", "--output", str(tmp_path / "never.tar.gz"),
    ], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 1
    assert "RUNTIME_TARGET_MISMATCH" in result.stderr
    assert not marker.exists()
    assert not (tmp_path / "never.tar.gz").exists()
