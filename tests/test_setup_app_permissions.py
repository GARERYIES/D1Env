"""Native app trust includes the whole bundle tree, not only its outer directory."""

import os
import plistlib
import threading
from pathlib import Path

import pytest
from test_setup_installer import app_at, fixture_installer

from d1env.setup.installer import MacInstaller
from d1env.setup.models import SetupError


@pytest.mark.parametrize("relative", ["Contents", "Contents/MacOS", "Contents/Resources/nested"])
def test_writable_nested_directory_never_reaches_signature_or_open(tmp_path, relative):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    directory = app / relative
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o777)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


@pytest.mark.parametrize("relative", ["Contents/Info.plist", "Contents/MacOS/com.docker.backend", "Contents/Resources/settings.json"])
def test_writable_internal_file_never_launches(tmp_path, relative):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    file = app / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_bytes(b"fixture")
    file.chmod(0o666)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


def test_foreign_owned_internal_file_never_launches(tmp_path, monkeypatch):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    leaf = app / "Contents/MacOS/com.docker.backend"
    actual = Path.lstat
    def foreign(path, *args, **kwargs):
        observed = actual(path, *args, **kwargs)
        if path == leaf:
            values = list(observed)
            values[4] = os.getuid() + 1
            return os.stat_result(values)
        return observed
    monkeypatch.setattr(Path, "lstat", foreign)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


@pytest.mark.parametrize("kind", ["outside", "broken", "cycle"])
def test_resource_symlink_must_resolve_to_owned_internal_bundle_tree(tmp_path, kind):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    resource = app / "Contents/Resources/link"
    resource.parent.mkdir()
    if kind == "outside":
        outside = tmp_path / "outside"
        outside.write_text("fixture")
        resource.symlink_to(outside)
    elif kind == "broken":
        resource.symlink_to("missing")
    else:
        resource.symlink_to("link")
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


def test_legitimate_framework_symlinks_are_allowed_without_executing_binary(tmp_path):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    framework = app / "Contents/Frameworks/Fixture.framework"
    (framework / "Versions/A/Resources").mkdir(parents=True)
    (framework / "Versions/A/Fixture").write_bytes(b"signed fixture data")
    (framework / "Versions/Current").symlink_to("A", target_is_directory=True)
    (framework / "Resources").symlink_to("Versions/Current/Resources", target_is_directory=True)
    (framework / "Fixture").symlink_to("Versions/Current/Fixture")
    installer.start(lock, threading.Event())
    assert native.calls[-1] == ("/usr/bin/open", "-a", str(app))
    assert all(call[0] != str(app / "Contents/MacOS/com.docker.backend") for call in native.calls)


@pytest.mark.parametrize("kind", ["missing", "wrong_identity", "traversal", "not_executable", "symlink"])
def test_bundle_main_executable_identity_and_permissions_are_checked(tmp_path, kind):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    info_path = app / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    executable = app / "Contents/MacOS/com.docker.backend"
    if kind == "missing":
        executable.unlink()
    elif kind == "wrong_identity":
        info["CFBundleExecutable"] = "OtherLauncher"
        info_path.write_bytes(plistlib.dumps(info))
    elif kind == "traversal":
        info["CFBundleExecutable"] = "../../untrusted"
        info_path.write_bytes(plistlib.dumps(info))
    elif kind == "not_executable":
        executable.chmod(0o644)
    else:
        data = executable.read_bytes()
        executable.unlink()
        other = app / "Contents/MacOS/other"
        other.write_bytes(data)
        other.chmod(0o755)
        executable.symlink_to("other")
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


def test_native_security_checks_do_not_cache_bundle_permissions(tmp_path):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    installer.start(lock, threading.Event())
    native.calls.clear()
    (app / "Contents/MacOS").chmod(0o777)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


def test_permission_change_during_signature_check_blocks_open(tmp_path):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app = applications / "Docker.app"
    app_at(app)
    actual = native.run
    def changed(argv, cancel, timeout_s=60):
        result = actual(argv, cancel, timeout_s)
        if argv[0] == "/usr/sbin/spctl":
            (app / "Contents/MacOS").chmod(0o777)
        return result
    native.run = changed
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert not any(call[0] == "/usr/bin/open" for call in native.calls)


def test_official_installed_app_permissions_are_checked_readonly():
    app = Path("/Applications/Docker.app")
    if not app.is_dir():
        pytest.skip("actual installed official Mac app is unavailable; hardware/install not verified")
    evidence = MacInstaller._check_app(app)
    assert evidence["executable"] == "com.docker.backend"
    assert evidence["permission_tree_verified"] is True
    assert evidence["app_entries_checked"] >= 700
