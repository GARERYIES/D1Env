import errno
import plistlib
import shutil
import threading
from pathlib import Path

import pytest
from test_setup_download import lock_for

from d1env.setup.installer import BoundedNativeRunner, MacInstaller, NativeResult
from d1env.setup.models import SetupError


def app_at(path, version="4.80.0"):
    (path / "Contents").mkdir(parents=True)
    (path / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "com.docker.docker", "CFBundleShortVersionString": version,
        "CFBundleVersion": "232116", "CFBundleExecutable": "com.docker.backend",
    }))
    (path / "Contents/MacOS").mkdir()
    executable = path / "Contents/MacOS/com.docker.backend"
    executable.write_bytes(b"signed fixture bytes; never executed")
    executable.chmod(0o755)


class NativeFake:
    def __init__(self, *, bad_signature=False, bad_gatekeeper=False):
        self.calls = []
        self.bad_signature = bad_signature
        self.bad_gatekeeper = bad_gatekeeper

    def run(self, argv, cancel, timeout_s=60):
        self.calls.append(argv)
        if argv[:2] == ("/usr/bin/hdiutil", "attach"):
            app_at(Path(argv[argv.index("-mountpoint") + 1]) / "Docker.app")
        if argv[0] == "/usr/bin/ditto":
            shutil.copytree(argv[-2], argv[-1])
        bad = ((argv[0] == "/usr/bin/codesign" and self.bad_signature)
               or (argv[0] == "/usr/sbin/spctl" and self.bad_gatekeeper))
        return NativeResult(1 if bad else 0, False)


def fixture_installer(tmp_path, fake=None, *, writable=True, renamer=None):
    applications = tmp_path / "Applications"
    applications.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    lock = lock_for()
    dmg = cache / (lock["sha256"] + ".dmg")
    dmg.write_bytes(b"official test bytes")
    dmg.chmod(0o600)
    native = fake or NativeFake()
    installer = MacInstaller(cache, runner=native, applications_dir=applications,
                             writable=lambda path: writable, renamer=renamer)
    return installer, native, dmg, applications, lock


def test_verified_mount_copy_atomic_install_and_detach(tmp_path):
    installer, native, dmg, applications, lock = fixture_installer(tmp_path, renamer=lambda src, dst: src.rename(dst))
    evidence = installer.install(dmg, lock, "a" * 32, threading.Event())
    assert evidence["installed"] is True
    assert evidence["signature_verified"] is True
    assert evidence["gatekeeper_verified"] is True
    assert (applications / "Docker.app/Contents/Info.plist").exists()
    assert native.calls[-1][0:2] == ("/usr/bin/hdiutil", "detach")
    requirement = next(call for call in native.calls if call[0] == "/usr/bin/codesign")
    assert '=identifier "com.docker.docker" and anchor apple generic and certificate leaf[subject.OU] = "9BNSXJN65R"' in requirement
    assert all("sudo" not in call and "--accept-license" not in call for call in native.calls)


@pytest.mark.parametrize("kind", ["signature", "gatekeeper", "hash", "cancelled"])
def test_rejected_installer_never_copies_or_launches_and_detaches(tmp_path, kind):
    native = NativeFake(bad_signature=kind == "signature", bad_gatekeeper=kind == "gatekeeper")
    installer, native, dmg, applications, lock = fixture_installer(tmp_path, native)
    if kind == "hash":
        dmg.write_bytes(b"x" * lock["size_bytes"])
    cancel = threading.Event()
    if kind == "cancelled":
        cancel.set()
    with pytest.raises(SetupError):
        installer.install(dmg, lock, "a" * 32, cancel)
    assert not (applications / "Docker.app").exists()
    assert not any(call[0] in {"/usr/bin/ditto", "/usr/bin/open"} for call in native.calls)
    if kind in {"signature", "gatekeeper"}:
        assert native.calls[-1][0:2] == ("/usr/bin/hdiutil", "detach")


def test_existing_application_is_never_overwritten(tmp_path):
    installer, native, dmg, applications, lock = fixture_installer(tmp_path)
    app_at(applications / "Docker.app", version="4.94.0")
    before = (applications / "Docker.app/Contents/Info.plist").read_bytes()
    result = installer.install(dmg, lock, "a" * 32, threading.Event())
    assert result["reused_existing"] is True
    assert before == (applications / "Docker.app/Contents/Info.plist").read_bytes()
    assert native.calls == []


def test_unwritable_applications_opens_only_verified_native_installer(tmp_path):
    installer, native, dmg, applications, lock = fixture_installer(tmp_path, writable=False)
    result = installer.install(dmg, lock, "a" * 32, threading.Event())
    assert result["native_setup_required"] is True
    assert not (applications / "Docker.app").exists()
    assert ("/usr/bin/open", str(dmg)) in native.calls
    assert not any(call[0] == "/usr/bin/ditto" for call in native.calls)
    # Finder must receive the DMG only after our verification mount is gone.
    detach_index = next(index for index, call in enumerate(native.calls)
                        if call[:2] == ("/usr/bin/hdiutil", "detach"))
    assert detach_index < native.calls.index(("/usr/bin/open", str(dmg)))
    assert native.calls[-1] == ("/usr/bin/open", str(dmg))


def test_cancel_after_verification_unmount_never_opens_native_window(tmp_path):
    cancelled = threading.Event()

    class CancelAfterDetach(NativeFake):
        def run(self, argv, cancel, timeout_s=60):
            result = super().run(argv, cancel, timeout_s)
            if argv[:2] == ("/usr/bin/hdiutil", "detach"):
                cancelled.set()
            return result

    installer, native, dmg, _applications, lock = fixture_installer(tmp_path, CancelAfterDetach(), writable=False)
    with pytest.raises(SetupError, match="SETUP_CANCELLED"):
        installer.install(dmg, lock, "a" * 32, cancelled)
    assert not any(call[0] == "/usr/bin/open" for call in native.calls)


def test_atomic_conflict_keeps_raced_in_app_and_only_removes_owned_staging(tmp_path):
    def race(src, dst):
        app_at(dst, "4.94.0")
        raise OSError(errno.EEXIST, "exists")
    installer, _native, dmg, applications, lock = fixture_installer(tmp_path, renamer=race)
    with pytest.raises(SetupError, match="EXISTING_DOCKER_PRESERVED"):
        installer.install(dmg, lock, "a" * 32, threading.Event())
    observed = plistlib.loads((applications / "Docker.app/Contents/Info.plist").read_bytes())
    assert observed["CFBundleShortVersionString"] == "4.94.0"
    assert list(applications.iterdir()) == [applications / "Docker.app"]


def test_launch_verifies_existing_app_before_fixed_open(tmp_path):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app_at(applications / "Docker.app", "4.94.0")
    installer.start(lock, threading.Event())
    assert native.calls[-1] == ("/usr/bin/open", "-a", str(applications / "Docker.app"))
    native.bad_signature = True
    native.calls.clear()
    with pytest.raises(SetupError, match="INSTALLER_SIGNATURE_REJECTED"):
        installer.start(lock, threading.Event())
    assert not any(call[0] == "/usr/bin/open" for call in native.calls)


def test_application_symlink_and_unexpected_mount_paths_rejected(tmp_path):
    installer, native, dmg, applications, lock = fixture_installer(tmp_path)
    victim = tmp_path / "other.app"
    app_at(victim)
    (applications / "Docker.app").symlink_to(victim, target_is_directory=True)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []
    with pytest.raises(SetupError, match="SETUP_TASK_ID_INVALID"):
        installer.install(dmg, lock, "../../x", threading.Event())


@pytest.mark.parametrize("writable", [True, False])
def test_failed_unmount_is_failure_and_preserves_installed_app(tmp_path, writable):
    class FailedUnmount(NativeFake):
        def run(self, argv, cancel, timeout_s=60):
            result = super().run(argv, cancel, timeout_s)
            return NativeResult(1, False) if argv[:2] == ("/usr/bin/hdiutil", "detach") else result
    installer, native, dmg, applications, lock = fixture_installer(tmp_path, FailedUnmount(),
                                                                writable=writable, renamer=lambda src, dst: src.rename(dst))
    with pytest.raises(SetupError, match="INSTALLER_UNMOUNT_FAILED"):
        installer.install(dmg, lock, "a" * 32, threading.Event())
    assert (applications / "Docker.app").exists() is writable
    assert list(applications.iterdir()) == ([applications / "Docker.app"] if writable else [])
    assert not any(call[0] == "/usr/bin/open" for call in native.calls)


def test_group_writable_existing_application_is_not_launched(tmp_path):
    installer, native, _dmg, applications, lock = fixture_installer(tmp_path)
    app_at(applications / "Docker.app")
    (applications / "Docker.app").chmod(0o775)
    with pytest.raises(SetupError, match="INSTALLER_APP_UNSAFE"):
        installer.start(lock, threading.Event())
    assert native.calls == []


def test_native_runner_rejects_arbitrary_binary_deadline_and_already_cancelled():
    runner = BoundedNativeRunner()
    with pytest.raises(SetupError, match="NATIVE_OPERATION_REJECTED"):
        runner.run(("/bin/bash", "-c", "anything"), threading.Event())
    with pytest.raises(SetupError, match="NATIVE_OPERATION_REJECTED"):
        runner.run(("/usr/bin/open", "/Applications/Docker.app"), threading.Event(), 301)
    event = threading.Event()
    event.set()
    with pytest.raises(SetupError, match="SETUP_CANCELLED"):
        runner.run(("/usr/bin/open", "/Applications/Docker.app"), event)


@pytest.mark.parametrize("cancel_during_operation", [False, True])
def test_native_runner_kills_only_its_process_group_on_cancel_or_timeout(monkeypatch, cancel_during_operation):
    import subprocess
    event = threading.Event()
    captured = {}
    killed = []
    monkeypatch.setenv("DYLD_INSERT_LIBRARIES", "/untrusted/library")
    monkeypatch.setenv("D1ENV_PRIVATE_VALUE", "test must not propagate")
    class Process:
        pid = 456789
        returncode = -9
        def poll(self):
            if cancel_during_operation:
                event.set()
        def wait(self):
            return -9
    def launch(argv, **kwargs):
        captured.update({"argv": argv, **kwargs})
        return Process()
    monkeypatch.setattr("d1env.setup.installer.subprocess.Popen", launch)
    monkeypatch.setattr("d1env.setup.installer.os.killpg", lambda pid, sig: killed.append(pid))
    runner = BoundedNativeRunner()
    if cancel_during_operation:
        with pytest.raises(SetupError, match="SETUP_CANCELLED"):
            runner.run(("/usr/bin/open", "-a", "/Applications/Docker.app"), event, 0.001)
    else:
        result = runner.run(("/usr/bin/open", "-a", "/Applications/Docker.app"), event, 0.001)
        assert result.timed_out is True and result.returncode is None
    assert killed == [456789]
    assert captured["shell"] is False and captured["stdin"] == subprocess.DEVNULL
    assert "DYLD_INSERT_LIBRARIES" not in captured["env"] and "D1ENV_PRIVATE_VALUE" not in captured["env"]
