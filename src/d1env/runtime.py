"""Locate trusted read-only assets separately from private writable state."""

import os
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    assets_dir: Path
    state_dir: Path


def _absolute(path: Path, code: str) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute() or ".." in expanded.parts:
        raise ValueError(f"{code}: 必须使用明确的绝对路径，不接受父目录跳转")
    return expanded


def _no_links(path: Path, code: str) -> None:
    for item in (*reversed(path.parents), path):
        if item.is_symlink():
            raise ValueError(f"{code}: 不接受符号链接或链接祖先目录")


def validate_assets_dir(path: Path) -> Path:
    """Validate the installed/source asset layout without writing to it."""
    path = _absolute(path, "ASSETS_INVALID")
    _no_links(path, "ASSETS_INVALID")
    required = (
        path / "frontend/dist/index.html", path / "docs/research/UPSTREAM_LOCK.json",
    )
    if not path.is_dir() or not (path / "profiles").is_dir():
        raise ValueError("ASSETS_MISSING: 缺少可信 Profile 或资源目录")
    if not any((path / "profiles").glob("*.yaml")) or any(not item.is_file() for item in required):
        raise ValueError("ASSETS_MISSING: 缺少已构建页面、Profile 或来源锁")
    entries = [path, *required]
    directories = [path / "profiles", path / "frontend/dist", path / "docs"]
    bundles = path / "bundles"
    if bundles.exists() or bundles.is_symlink():
        _no_links(bundles, "ASSETS_INVALID")
        if not bundles.is_dir():
            raise ValueError("ASSETS_INVALID: 配套工件资源必须使用普通目录")
        directories.append(bundles)
    for directory in directories:
        entries.append(directory)
        entries.extend(directory.rglob("*"))
    for item in entries:
        _no_links(item, "ASSETS_INVALID")
        observed = item.lstat()
        if not (stat.S_ISDIR(observed.st_mode) or stat.S_ISREG(observed.st_mode)):
            raise ValueError("ASSETS_INVALID: 资源必须为普通文件或目录")
        if observed.st_uid not in {0, os.getuid()} or observed.st_mode & (stat.S_IWOTH | stat.S_IWGRP):
            raise ValueError("ASSETS_INVALID: 资源必须归属当前用户或 root，不能允许其他用户/组修改")
    return path


def ensure_private_state_dir(path: Path) -> Path:
    """Create an owner-controlled state directory; reject unsafe existing paths."""
    path = _absolute(path, "STATE_INVALID")
    _no_links(path, "STATE_UNSAFE")
    uid = os.getuid()
    for item in (*reversed(path.parents), path):
        try:
            observed = item.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(observed.st_mode):
            raise ValueError("STATE_UNSAFE: 状态路径及祖先必须是目录")
        if observed.st_uid not in {0, uid} or (item == path and observed.st_uid != uid):
            raise ValueError("STATE_OWNER_MISMATCH: 状态目录不属于当前运行用户")
        if observed.st_mode & (stat.S_IWOTH | stat.S_IWGRP):
            sticky_parent = item != path and observed.st_uid == 0 and observed.st_mode & stat.S_ISVTX
            if not sticky_parent:
                raise ValueError("STATE_UNSAFE: 状态目录不能允许其他用户任意写入")
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ValueError("STATE_UNAVAILABLE: 无法创建用户状态目录，请检查路径与权限") from exc
    _no_links(path, "STATE_UNSAFE")
    observed = path.lstat()
    if observed.st_uid != uid or observed.st_mode & (stat.S_IWOTH | stat.S_IWGRP):
        raise ValueError("STATE_UNSAFE: 新建状态目录的归属或权限发生变化")
    return path


def resolve_runtime_paths(
    source_root: Path | None = None, *, environ: Mapping[str, str] | None = None,
) -> RuntimePaths:
    """Resolve frozen/package assets or an explicit development checkout.

    Overrides are local launcher inputs, never values accepted from the Web API.
    They retain the source launcher's state-directory override without coupling an
    installed read-only bundle to the source checkout's work/ directory.
    """
    env = os.environ if environ is None else environ
    frozen_root = getattr(sys, "_MEIPASS", None)
    if env.get("D1ENV_ASSETS_DIR"):
        assets = Path(env["D1ENV_ASSETS_DIR"])
    elif source_root is not None:
        assets = source_root.absolute()
    elif frozen_root is not None:
        assets = Path(frozen_root) / "assets"
    elif (Path(__file__).parent / "_assets").is_dir():
        assets = Path(__file__).parent / "_assets"
    else:
        assets = Path(__file__).resolve().parents[2]
    assets = validate_assets_dir(assets)
    if env.get("D1ENV_STATE_DIR"):
        state = Path(env["D1ENV_STATE_DIR"])
    elif sys.platform == "darwin":
        state = Path.home() / "Library/Application Support/D1Env"
    else:
        base = Path(env["XDG_STATE_HOME"]) if env.get("XDG_STATE_HOME") else Path.home() / ".local/state"
        state = base / "d1env"
    state = ensure_private_state_dir(state)
    return RuntimePaths(assets_dir=assets, state_dir=state)
