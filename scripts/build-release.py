#!/usr/bin/env python3
"""Build data assets or a native portable runtime from trusted locked inputs."""

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from d1env.runtime import ensure_private_state_dir, validate_assets_dir


def build_asset_bundle(source_root: Path, output: Path, bundle_id: str) -> dict[str, object]:
    root = validate_assets_dir(source_root.absolute())
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", bundle_id):
        raise ValueError("BUNDLE_ID_INVALID: 使用明确的数据包标识")
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("OUTPUT_EXISTS: 不覆盖已有发行文件")
    parent = ensure_private_state_dir(output.parent)
    files = sorted((root / "profiles").glob("*.yaml"))
    files.extend(sorted(item for item in (root / "frontend/dist").rglob("*") if item.is_file()))
    files.append(root / "docs/research/UPSTREAM_LOCK.json")
    notice = root / "THIRD_PARTY_NOTICES.md"
    if notice.is_file() and not notice.is_symlink():
        files.append(notice)
    records: list[dict[str, object]] = []
    payloads: list[tuple[str, bytes]] = []
    for file in sorted(files):
        relative = "payload/" + file.relative_to(root).as_posix()
        data = file.read_bytes()
        records.append({"path": relative, "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
        payloads.append((relative, data))
    manifest = {"schema_version": 1, "kind": "d1env_data_bundle", "bundle_id": bundle_id,
                "files": records}
    descriptor, temporary = tempfile.mkstemp(prefix=".d1env-assets-", suffix=".zip", dir=parent)
    os.close(descriptor)
    stage = Path(temporary)
    try:
        with zipfile.ZipFile(stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            entries = [("d1env-offline.json", json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                                                       separators=(",", ":")).encode()), *payloads]
            for name, data in entries:
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o600) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, data)
        digest = hashlib.sha256(stage.read_bytes()).hexdigest()
        os.link(stage, output)  # Atomic no-overwrite publication on the same filesystem.
    finally:
        stage.unlink(missing_ok=True)
    return {"kind": "d1env_data_bundle", "bundle_id": bundle_id, "sha256": digest,
            "size_bytes": output.stat().st_size, "self_contained_runtime": False,
            "scope": "assets_only", "file_count": len(records)}


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=180, env=env)
    if result.returncode:
        raise ValueError(f"BUILD_OPERATION_FAILED: exit={result.returncode}; {result.stderr[-2400:]}")
    return result.stdout


def copy_ros_bundle(source: Path, assets_dir: Path, architecture: str) -> dict[str, object]:
    """Copy only the fixed ROS data archive selected by the installed wheel lock.

    This is pure-file acquisition, never an image import or Docker readiness check.
    The Docker Desktop installer is not an accepted or bundled payload.
    """
    stage: Path | None = None
    created_directory = False
    directory = assets_dir / "bundles"
    try:
        assets_dir = validate_assets_dir(assets_dir.absolute())
        directory = assets_dir / "bundles"
        lock = assets_dir / "docs/build/ROS_PROBE_OFFLINE.json"
        if not lock.is_file() or lock.stat().st_size > 1024**2:
            raise ValueError("ROS_BUNDLE_LOCK_INVALID: 安装后 wheel 缺少受信 ROS 工件来源锁")
        raw = json.loads(lock.read_bytes())
        if (not isinstance(raw, dict) or type(raw.get("schema_version")) is not int
                or raw["schema_version"] != 1 or architecture not in {"aarch64", "x86_64"}
                or raw.get("architecture") != architecture or raw.get("source") != "d1env/ros-probe"
                or raw.get("filename") != f"d1env-ros-probe-m3-{architecture}.tar"
                or type(raw.get("size_bytes")) is not int or not 0 < raw["size_bytes"] <= 2 * 1024**3
                or not isinstance(raw.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]) or raw["sha256"] == "0" * 64
                or not isinstance(raw.get("image_id"), str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", raw["image_id"])
                or raw["image_id"] == "sha256:" + "0" * 64):
            raise ValueError("ROS_BUNDLE_LOCK_INVALID: 来源锁文件名、架构、来源、不可变 ID 或摘要/大小无效")
        destination = directory / raw["filename"]
        if destination.exists() or destination.is_symlink():
            raise ValueError("ROS_BUNDLE_EXISTS: 不覆盖已有配套工件或链接")
        source = source.absolute()
        if any(item.is_symlink() for item in (*source.parents, source)):
            raise ValueError("ROS_BUNDLE_UNSAFE: 输入归档及其祖先不能使用链接")
        descriptor = os.open(source, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as contents:
            observed = os.fstat(contents.fileno())
            if (not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1
                    or observed.st_uid not in {0, os.getuid()}
                    or observed.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
                raise ValueError("ROS_BUNDLE_UNSAFE: 输入必须为当前用户/root 的普通独占文件，不能允许组/其他用户改写")
            if observed.st_size != raw["size_bytes"]:
                raise ValueError("ROS_BUNDLE_MISMATCH: 输入归档实际大小不符合安装工件锁")
            digest = hashlib.sha256()
            remaining = raw["size_bytes"]
            while remaining:
                chunk = contents.read(min(1024**2, remaining))
                if not chunk:
                    raise ValueError("ROS_BUNDLE_MISMATCH: 输入归档被截断")
                digest.update(chunk)
                remaining -= len(chunk)
            if contents.read(1) or digest.hexdigest() != raw["sha256"]:
                raise ValueError("ROS_BUNDLE_MISMATCH: 输入归档 SHA-256/大小不符合安装工件锁")
            contents.seek(0)
            if not directory.exists():
                directory.mkdir(mode=0o755)
                created_directory = True
            validate_assets_dir(assets_dir)
            handle, name = tempfile.mkstemp(prefix=".d1env-ros-", dir=directory)
            stage = Path(name)
            copied_digest = hashlib.sha256()
            remaining = raw["size_bytes"]
            with os.fdopen(handle, "wb") as target:
                while remaining:
                    chunk = contents.read(min(1024**2, remaining))
                    if not chunk:
                        raise ValueError("ROS_BUNDLE_MISMATCH: 复制时输入归档被截断")
                    target.write(chunk)
                    copied_digest.update(chunk)
                    remaining -= len(chunk)
                if contents.read(1) or copied_digest.hexdigest() != raw["sha256"]:
                    raise ValueError("ROS_BUNDLE_MISMATCH: 输入归档复制期间发生变化")
                target.flush()
                os.fsync(target.fileno())
            stage.chmod(0o644)
            os.link(stage, destination)  # Atomic no-overwrite publication of verified bytes.
        return {key: raw[key] for key in ("filename", "sha256", "size_bytes", "source", "image_id", "architecture")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("ROS_BUNDLE"):
            raise
        raise ValueError("ROS_BUNDLE_UNSAFE: 无法安全读取或发布固定 ROS 归档") from exc
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
        if created_directory:
            try:
                directory.rmdir()  # Remove only our empty staging directory on failure.
            except OSError:
                pass


def _runtime_source(runtime: Path) -> Path:
    runtime = runtime.absolute()
    python = runtime / "bin/python3.10"
    required = (python, runtime / "lib/python3.10/json/__init__.py",
                runtime / "lib/python3.10/ssl.py", runtime / "lib/python3.10/ctypes/__init__.py",
                runtime / "lib/python3.10/LICENSE.txt")
    if not runtime.is_dir() or any(not path.is_file() for path in required):
        raise ValueError("RUNTIME_INCOMPLETE: 必须提供含解释器、完整标准库和动态库的 CPython 3.10 目录")
    if not any(path.name.startswith("libpython3.10") for path in (runtime / "lib").iterdir()):
        raise ValueError("RUNTIME_INCOMPLETE: 缺少与解释器配套的 libpython")
    for path in runtime.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(runtime):
            raise ValueError("RUNTIME_UNSAFE: 完整运行时不能链接到包外的系统或开发目录")
    return runtime


def _runtime_facts(python: Path, env: dict[str, str]) -> dict[str, object]:
    script = ("import json,platform,sys,ssl,ctypes; print(json.dumps({'python_version':"
              "platform.python_version(),'platform':'macos' if sys.platform=='darwin' else sys.platform,"
              "'architecture':{'arm64':'aarch64','AMD64':'x86_64'}.get(platform.machine(),platform.machine()),"
              "'prefix':sys.prefix}))")
    facts: dict[str, object] = json.loads(_run([str(python), "-I", "-S", "-B", "-c", script], env=env))
    if not str(facts["python_version"]).startswith("3.10."):
        raise ValueError("RUNTIME_VERSION_MISMATCH: 当前构建固定 CPython 3.10")
    return facts


def _locked_requirements(raw: bytes) -> None:
    pending = ""
    count = 0
    for original in raw.decode("utf-8").splitlines():
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        continued = line.endswith("\\")
        pending += " " + (line[:-1].strip() if continued else line)
        if continued:
            continue
        hashes = re.findall(r"--hash=sha256:[0-9a-f]{64}", pending)
        requirement = re.sub(r"\s*--hash=sha256:[0-9a-f]{64}", "", pending).strip()
        if (not hashes or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9_.!+\-]+(?:\s*;\s*[^@\\]+)?", requirement)
                or any(token in requirement for token in ("--", "://", "@", "\x00"))):
            raise ValueError("REQUIREMENTS_UNLOCKED: 只接受固定版本、明确 hash 的 uv runtime 导出，不接受任意安装参数")
        count += 1
        pending = ""
    if pending.strip() or not count:
        raise ValueError("REQUIREMENTS_UNLOCKED: 锁定依赖清单不完整")


def _wheel_metadata(raw: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
        names = wheel.namelist()
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise ValueError("WHEEL_INVALID: 缺少唯一项目元数据")
        metadata = BytesParser().parsebytes(wheel.read(metadata_paths[0]))
        if metadata["Name"] != "d1env":
            raise ValueError("WHEEL_INVALID: 只能打包本项目 d1env wheel")
        required = {"d1env/_assets/frontend/dist/index.html",
                    "d1env/_assets/docs/research/UPSTREAM_LOCK.json"}
        if not required.issubset(names) or not any(name.startswith("d1env/_assets/profiles/") for name in names):
            raise ValueError("WHEEL_ASSETS_MISSING: wheel 必须包含页面、Profile 和来源锁")
        return {"name": metadata["Name"], "version": metadata["Version"]}


def _tree_records(root: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            target = str(path.readlink())
            if Path(target).is_absolute() or not path.resolve().is_relative_to(root):
                raise ValueError("RUNTIME_UNSAFE: 发行资源链接不能离开包内")
            data = target.encode()
            kind = "symlink"
        elif path.is_file():
            data = path.read_bytes()
            kind = "file"
        else:
            raise ValueError("RUNTIME_UNSAFE: 不打包特殊文件")
        result.append({"path": name, "type": kind, "size_bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "mode": stat.S_IMODE(path.lstat().st_mode)})
    return result


def _runtime_archive_records(source: Path) -> list[dict[str, object]]:
    """Inspect the already hash-verified source without extracting or executing it."""
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    with tarfile.open(source, "r:gz") as archive:
        for item in archive:
            parts = item.name.split("/")
            if (parts[0] != "python" or len(parts) < 2 or any(part in {"", ".", ".."} for part in parts)
                    or "\\" in item.name or item.name in seen):
                raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 源归档含异常或重复路径")
            seen.add(item.name)
            if item.isdir():
                continue
            path = "/".join(parts[1:])
            if item.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), item.linkname))
                if item.linkname.startswith("/") or target == ".." or target.startswith("../"):
                    raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 源归档链接离开运行时")
                data = item.linkname.encode()
                kind, mode = "symlink", item.mode & 0o755
            elif item.isfile() and item.sparse is None and item.size <= 268435456:
                payload = archive.extractfile(item)
                if payload is None:
                    raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 源归档文件不可读")
                with payload:
                    data = payload.read()
                # Match safe extraction's data-filter permission normalization.
                mode = item.mode & 0o755
                if not mode & 0o100:
                    mode &= ~0o111
                mode |= 0o600
                kind = "file"
            else:
                raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 源归档含硬链接/特殊/超大文件")
            records.append({"path": path, "type": kind, "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(), "mode": mode})
    return sorted(records, key=lambda item: Path(str(item["path"])))


def _source_provenance(record: Path | None, source: Path | None,
                       source_tree_sha: str, target_platform: str, architecture: str) -> dict[str, object]:
    if record is None and source is None:
        return {"status": "blocked", "download_url": None, "download_archive_sha256": None,
                "upstream_commit": None, "build_tool_commit": None, "cpython_source_commit": None,
                "local_license_path": "runtime/lib/python3.10/LICENSE.txt",
                "bundled_library_license_completeness": "blocked"}
    if record is None or source is None:
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 来源锁与原下载归档必须同时提供")
    if record.is_symlink() or source.is_symlink() or record.stat().st_size > 65536:
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 来源锁/归档不能使用链接，来源锁大小受限")
    raw = json.loads(record.read_bytes())
    required = {"schema_version", "kind", "retrieval_status", "python_version", "platform", "architecture",
                "download_url", "download_archive_sha256", "download_archive_size_bytes",
                "runtime_source_tree_sha256", "tree_hash_algorithm", "build_tool_repository",
                "build_tool_tag", "build_tool_commit", "cpython_source_commit", "commit_scope", "licenses",
                "evidence", "release_signature_verified", "scope"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 来源锁字段无效")
    url = urlsplit(str(raw["download_url"]))
    if (type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["kind"] != "d1env_python_runtime_source" or raw["retrieval_status"] != "verified"
            or raw["python_version"] != "3.10.20" or raw["platform"] != target_platform
            or raw["architecture"] != architecture
            or raw["build_tool_repository"] != "https://github.com/astral-sh/python-build-standalone"
            or not re.fullmatch(r"[0-9]{8}", str(raw["build_tool_tag"]))
            or not re.fullmatch(r"[0-9a-f]{40}", str(raw["build_tool_commit"]))
            or raw["build_tool_commit"] == "0" * 40 or raw["cpython_source_commit"] is not None
            or url.scheme != "https" or url.netloc != "github.com" or url.query or url.fragment
            or not url.path.startswith("/astral-sh/python-build-standalone/releases/download/" + str(raw["build_tool_tag"]) + "/")
            or type(raw["download_archive_size_bytes"]) is not int
            or raw["download_archive_size_bytes"] <= 0):
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 来源锁的平台、官方来源或版本字段无效")
    expected_sha = raw["download_archive_sha256"]
    if (not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
            or expected_sha == "0" * 64 or not source.is_file()
            or source.stat().st_size != raw["download_archive_size_bytes"]
            or hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha):
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 源归档实际 SHA-256/大小与可信来源锁不符")
    archive_records = _runtime_archive_records(source)
    archive_tree_sha = hashlib.sha256(json.dumps(archive_records, sort_keys=True).encode()).hexdigest()
    if archive_tree_sha != raw["runtime_source_tree_sha256"] or source_tree_sha != archive_tree_sha:
        raise ValueError("RUNTIME_PROVENANCE_MISMATCH: 实际运行时/安全源归档树与可信来源锁不一致")
    return {"status": "verified", "download_url": raw["download_url"],
            "download_archive_sha256": expected_sha, "download_archive_size_bytes": raw["download_archive_size_bytes"],
            "runtime_source_tree_sha256": archive_tree_sha, "build_tool_repository": raw["build_tool_repository"],
            "build_tool_tag": raw["build_tool_tag"], "build_tool_commit": raw["build_tool_commit"],
            "cpython_source_commit": None, "source_lock_sha256": hashlib.sha256(record.read_bytes()).hexdigest(),
            "verification": "trusted source lock matched to archive SHA/size and full runtime file tree before interpreter execution",
            "local_license_path": "runtime/lib/python3.10/LICENSE.txt", "release_signature_verified": False,
            "bundled_library_license_completeness": "blocked"}


def build_portable_bundle(runtime: Path, wheel: Path, requirements: Path, output: Path,
                          target_platform: str, architecture: str, uv: Path | None,
                          cache_dir: Path | None = None, allow_downloads: bool = False,
                          runtime_provenance_json: Path | None = None,
                          runtime_source_archive: Path | None = None,
                          ros_bundle: Path | None = None) -> dict[str, object]:
    runtime = _runtime_source(runtime)
    requirements_bytes = requirements.read_bytes()
    _locked_requirements(requirements_bytes)
    wheel_bytes = wheel.read_bytes()
    project = _wheel_metadata(wheel_bytes)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("OUTPUT_EXISTS: 不覆盖已有运行包")
    parent = ensure_private_state_dir(output.parent)
    uv_binary = str(uv) if uv is not None else shutil.which("uv")
    if not uv_binary:
        raise ValueError("BUILD_TOOL_MISSING: 构建机需要已有 uv；终端用户不需要 uv")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTHON", "UV_", "PIP_", "DYLD_", "LD_")) and key != "VIRTUAL_ENV"}
    # uv checks the exported requirement hashes again; a missing cache fails closed
    # rather than silently depending on a network during a reproducible build.
    cache = cache_dir.absolute() if cache_dir else Path(_run(
        [uv_binary, "--no-config", "cache", "dir"], env=env).strip())
    env.update({"UV_PYTHON_DOWNLOADS": "never", "UV_LINK_MODE": "copy",
                "UV_CACHE_DIR": str(cache)})
    original_records = _tree_records(runtime)
    runtime_source_sha = hashlib.sha256(json.dumps(original_records, sort_keys=True).encode()).hexdigest()
    provenance = _source_provenance(runtime_provenance_json, runtime_source_archive, runtime_source_sha,
                                    target_platform, architecture)
    provenance["local_build_marker"] = (runtime / "BUILD").read_text().strip() if (runtime / "BUILD").is_file() else None
    original_facts = _runtime_facts(runtime / "bin/python3.10", env)
    if original_facts["platform"] != target_platform or original_facts["architecture"] != architecture:
        raise ValueError("RUNTIME_TARGET_MISMATCH: 实际运行时平台/架构与发行标识不一致，不伪装 Linux 或其他 CPU")
    bundle_name = f"D1Env-{project['version']}-{target_platform}-{architecture}"
    with tempfile.TemporaryDirectory(prefix=".d1env-release-", dir=parent) as temporary:
        stage = Path(temporary)
        bundle = stage / bundle_name
        copied_runtime = bundle / "runtime"
        shutil.copytree(runtime, copied_runtime, symlinks=True)
        python = copied_runtime / "bin/python3.10"
        site_packages = copied_runtime / "lib/python3.10/site-packages"
        if site_packages.is_dir():
            shutil.rmtree(site_packages)  # Clean only the new copied runtime, never the supplied source.
        site_packages.mkdir(mode=0o755)
        copied_facts = _runtime_facts(python, env)
        if Path(str(copied_facts["prefix"])) != copied_runtime:
            raise ValueError("RUNTIME_NOT_RELOCATABLE: 复制后的解释器仍引用包外前缀")
        inputs = stage / "inputs"
        inputs.mkdir()
        locked = inputs / "requirements.txt"
        locked.write_bytes(requirements_bytes)
        locked_wheel = inputs / wheel.name
        locked_wheel.write_bytes(wheel_bytes)
        base = [uv_binary, "--no-config", *([] if allow_downloads else ["--offline"]),
                "pip", "install", "--python", str(python),
                "--target", str(site_packages), "--no-deps", "--only-binary", ":all:"]
        _run([*base, "--require-hashes", "--default-index", "https://pypi.org/simple", "-r", str(locked)], env=env)
        wheel_sha = hashlib.sha256(wheel_bytes).hexdigest()
        local_requirement = inputs / "project.txt"
        local_requirement.write_text(f"d1env @ {locked_wheel.as_uri()} --hash=sha256:{wheel_sha}\n")
        _run([*base, "--no-index", "--require-hashes", "-r", str(local_requirement)], env=env)
        bundled_ros = (copy_ros_bundle(ros_bundle, site_packages / "d1env/_assets", architecture)
                       if ros_bundle is not None else None)
        for path in site_packages.rglob("*.pth"):
            content = path.read_text()
            if "editable" in path.name or "__editable__" in content or any(line.startswith("/") for line in content.splitlines()):
                path.unlink()
        for path in site_packages.glob("d1env-*.dist-info/direct_url.json"):
            path.unlink()  # Private build paths are replaced by actual wheel SHA in release provenance.
        if (site_packages / "bin").is_dir():
            shutil.rmtree(site_packages / "bin")  # Newly installed developer console wrappers are unused.
        for path in copied_runtime.rglob("__pycache__"):
            shutil.rmtree(path)
        launcher = bundle / "d1env.sh"
        launcher.write_text("#!/bin/sh\nset -eu\nD1ENV_BUNDLE_DIR=${0%/*}\nif [ \"$D1ENV_BUNDLE_DIR\" = \"$0\" ]; then D1ENV_BUNDLE_DIR=.; fi\nD1ENV_BUNDLE_ROOT=$(CDPATH= cd -- \"$D1ENV_BUNDLE_DIR\" && pwd)\nif [ \"$#\" -eq 0 ]; then set -- ui --demo; fi\nexec \"$D1ENV_BUNDLE_ROOT/runtime/bin/python3.10\" -I -B -m d1env.cli \"$@\"\n")
        launcher.chmod(0o755)
        if target_platform == "macos":
            clickable = bundle / "D1Env.command"
            clickable.write_text(launcher.read_text())
            clickable.chmod(0o755)
        (bundle / "REQUIREMENTS.txt").write_bytes(requirements_bytes)
        metadata_script = ("import importlib.metadata as m,json; print(json.dumps(sorted([{'name':d.metadata['Name'],"
                           "'version':d.version} for d in m.distributions()],key=lambda x:x['name'].lower())))")
        distributions = json.loads(_run([str(python), "-I", "-B", "-c", metadata_script], env=env))
        records = _tree_records(bundle)
        manifest = {"schema_version": 1, "kind": "d1env_portable_runtime", "project": project,
                    "platform": target_platform, "architecture": architecture,
                    "runtime": {key: value for key, value in copied_facts.items() if key != "prefix"},
                    "runtime_source_tree_sha256": runtime_source_sha, "wheel_sha256": wheel_sha,
                    "requirements_sha256": hashlib.sha256(requirements_bytes).hexdigest(),
                    "installed_distributions": distributions, "files": records,
                    "scope": "software_tool_candidate", "self_contained_runtime": True,
                    "build_dependency_source": "hash_locked_cache" if not allow_downloads else "hash_locked_cache_or_pypi",
                    "runtime_provenance": provenance,
                    "bundled_ros_image": bundled_ros,
                    "signed_release": False,
                    "linux_fresh_vm_verified": False, "robot_verified": False}
        (bundle / "D1ENV-RELEASE.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
        candidate = stage / "candidate.tar.gz"
        with (
            candidate.open("wb") as archive_file,
            gzip.GzipFile(filename="", fileobj=archive_file, mode="wb", mtime=0) as compressed,
            tarfile.open(fileobj=compressed, mode="w") as archive,
        ):
            for path in [bundle, *sorted(bundle.rglob("*"))]:
                info = archive.gettarinfo(str(path), arcname=path.relative_to(stage).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if info.isfile():
                    with path.open("rb") as contents:
                        archive.addfile(info, contents)
                else:
                    archive.addfile(info)
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        size = candidate.stat().st_size
        os.link(candidate, output)
    return {"kind": "d1env_portable_runtime", "platform": target_platform,
            "architecture": architecture, "project_version": project["version"],
            "bundle_directory": bundle_name, "sha256": digest, "size_bytes": size,
            "self_contained_runtime": True, "linux_fresh_vm_verified": False, "robot_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="构建已编译资源数据包；不是 Linux 安装器")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle-id", default="d1env-assets")
    parser.add_argument("--portable", action="store_true", help="完整本平台运行时与锁定 wheel 的便携候选")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--runtime-provenance-json", type=Path, help="受信官方运行时来源锁")
    parser.add_argument("--runtime-source-archive", type=Path, help="与来源锁匹配的原下载归档")
    parser.add_argument("--ros-bundle", type=Path, help="按安装后来源锁核对并内置 ROS 数据归档；不内置 Docker 安装器")
    parser.add_argument("--uv", type=Path)
    parser.add_argument("--cache-dir", type=Path, help="可信构建缓存；仍须满足锁定依赖 SHA-256")
    parser.add_argument("--allow-downloads", action="store_true", help="研发首次填充缓存时显式允许 HTTPS 下载；默认离线")
    parser.add_argument("--platform", choices=["macos", "linux"], default="macos" if sys.platform == "darwin" else "linux")
    parser.add_argument("--architecture", choices=["aarch64", "x86_64"], default={"arm64": "aarch64", "AMD64": "x86_64"}.get(platform.machine(), platform.machine()))
    args = parser.parse_args()
    try:
        if args.portable:
            if args.runtime is None or args.wheel is None or args.requirements is None:
                raise ValueError("PORTABLE_INPUTS_MISSING: 显式提供完整 runtime、实际 wheel 与 hash 锁定依赖")
            metadata = build_portable_bundle(args.runtime, args.wheel, args.requirements, args.output,
                                             args.platform, args.architecture, args.uv,
                                             args.cache_dir, args.allow_downloads,
                                             args.runtime_provenance_json, args.runtime_source_archive,
                                             args.ros_bundle)
        else:
            if args.ros_bundle is not None:
                raise ValueError("ROS_BUNDLE_PORTABLE_ONLY: 内置 ROS 工件只用于完整便携运行包")
            metadata = build_asset_bundle(args.source_root, args.output, args.bundle_id)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"资源打包失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
