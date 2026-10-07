import json
import os
import threading
import time

import pytest
from test_setup_download import lock_for

from d1env.setup.manager import SetupManager
from d1env.setup.models import SetupError


def ready_host(**updates):
    return {"docker_available": True, "docker_accessible": True, "compose_available": True,
            "docker_os": "linux", "docker_architecture": "aarch64", "endpoint_local": True,
            "docker_error": None, "disk_free_bytes": 5 * 1024**3, **updates}


def missing_host():
    return ready_host(docker_available=False, docker_accessible=False, compose_available=False,
                      docker_os=None, docker_architecture=None, endpoint_local=None,
                      docker_error="missing")

class DownloaderFake:
    def __init__(self, tmp_path):
        self.path = tmp_path / "official.dmg"
        self.calls = 0
    def fetch(self, lock, cancel, progress):
        self.calls += 1
        progress(lock["size_bytes"], lock["size_bytes"])
        return self.path


class InstallerFake:
    def __init__(self):
        self.exists = False
        self.calls = []
        self.needs_user = False
        self.on_start = lambda: None
    def app_exists(self):
        return self.exists
    def install(self, path, lock, task_id, cancel):
        self.calls.append("install")
        if self.needs_user:
            return {"installed": False, "native_setup_required": True}
        self.exists = True
        return {"installed": True, "signature_verified": True, "gatekeeper_verified": True}
    def start(self, lock, cancel):
        self.calls.append("start")
        self.on_start()
        return {"opened_application": True, "signature_verified": True, "gatekeeper_verified": True}


def manager_at(tmp_path, *, host=None, image=None, importer=None, platform=None, native=None):
    host = host if host is not None else ready_host()
    image = image if image is not None else {"artifact_ready": True, "image_id": "sha256:" + "a" * 64}
    downloader = DownloaderFake(tmp_path)
    native = native or InstallerFake()
    imported = []
    def prepare_image(is_cancelled):
        imported.append(True)
        if importer:
            return importer()
        image["artifact_ready"] = True
        return {"artifact_ready": True, "evidence": {"image_id": image["image_id"]}}
    manager = SetupManager(tmp_path, installer_lock=lock_for(), probe=lambda: dict(host),
                           image_probe=lambda: dict(image), prepare_image=prepare_image,
                           platform=platform or {"os_name": "Darwin", "architecture": "aarch64", "os_version": "26.0"},
                           downloader=downloader, native=native, wait_timeout_s=0.05, wait_interval_s=0.01)
    return manager, host, image, downloader, native, imported


def wait_terminal(manager, task_id, states=("SUCCEEDED", "FAILED", "WAITING_USER", "CANCELLED")):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        task = manager.get(task_id)
        if task["state"] in states:
            return task
        time.sleep(0.01)
    raise AssertionError("setup worker did not finish")


def test_existing_ready_environment_reused_and_current_status_rechecks(tmp_path):
    manager, host, image, downloader, native, imported = manager_at(tmp_path)
    task = manager.prepare("reuse-key-0001")
    done = wait_terminal(manager, task["task_id"])
    assert done["state"] == "SUCCEEDED"
    assert done["scope"] == "runtime_environment"
    assert done["environment_ready"] is True
    assert downloader.calls == 0 and native.calls == []
    assert imported == [True]
    assert manager.prepare("reuse-key-0001")["task_id"] == task["task_id"]
    host["docker_accessible"] = None
    host["docker_error"] = "timeout"
    assert manager.status()["environment_ready"] is None
    assert manager.get(task["task_id"])["environment_ready"] is None
    image["artifact_ready"] = 1  # Literal true only, never truthiness.
    host.update(ready_host())
    assert manager.status()["environment_ready"] is None
    assert len(imported) == 1


def test_missing_mac_requires_explicit_license_then_fixed_preparation(tmp_path):
    manager, host, _image, downloader, native, imported = manager_at(tmp_path, host=missing_host(), image={"artifact_ready": False, "image_id": "sha256:" + "a" * 64})
    native.on_start = lambda: host.update(ready_host())
    task = manager.prepare("install-key-0001")
    waiting = wait_terminal(manager, task["task_id"])
    assert waiting["state"] == "WAITING_USER" and waiting["user_action"] == "accept_license"
    assert downloader.calls == 0 and native.calls == []
    manager.continue_task(task["task_id"], "accept_license")
    done = wait_terminal(manager, task["task_id"])
    assert done["state"] == "SUCCEEDED" and done["environment_ready"] is True
    assert done["license_accepted"] is True
    assert native.calls == ["install", "start"] and downloader.calls == 1
    assert imported == [True]
    assert all(event["scope"] == "runtime_environment" for event in done["events"])


def test_native_system_permissions_are_waiting_and_check_again_does_not_download_twice(tmp_path):
    manager, host, _image, downloader, native, _imported = manager_at(tmp_path, host=missing_host())
    native.needs_user = True
    task = manager.prepare("native-key-0001")
    wait_terminal(manager, task["task_id"])
    manager.continue_task(task["task_id"], "accept_license")
    waiting = wait_terminal(manager, task["task_id"])
    assert waiting["stage"] == "native_setup" and waiting["user_action"] == "check_again"
    manager.continue_task(task["task_id"], "check_again")
    waiting = wait_terminal(manager, task["task_id"])
    assert waiting["state"] == "WAITING_USER"
    assert downloader.calls == 1 and native.calls == ["install"]
    native.exists = True  # A user completed the native system window.
    native.on_start = lambda: host.update(ready_host())
    manager.continue_task(task["task_id"], "check_again")
    assert wait_terminal(manager, task["task_id"])["state"] == "SUCCEEDED"
    assert native.calls == ["install", "start"]


@pytest.mark.parametrize("patch,code", [
    ({"docker_accessible": False, "docker_error": "permission_denied"}, "DOCKER_PERMISSION_DENIED"),
    ({"endpoint_local": False}, "DOCKER_ENDPOINT_UNSAFE"),
    ({"docker_architecture": "x86_64"}, "DOCKER_PLATFORM_UNSUPPORTED"),
    ({"docker_os": "windows"}, "DOCKER_PLATFORM_UNSUPPORTED"),
    ({"compose_available": False}, "COMPOSE_UNAVAILABLE"),
    ({"disk_free_bytes": 0}, "SETUP_DISK_SPACE"),
])
def test_existing_runtime_errors_never_install_replace_or_escalate(tmp_path, patch, code):
    manager, _host, _image, downloader, native, imported = manager_at(tmp_path, host=ready_host(**patch))
    task = manager.prepare("blocked-key-0001")
    done = wait_terminal(manager, task["task_id"])
    assert done["state"] == "FAILED"
    assert done["error"]["code"] == code
    assert downloader.calls == 0 and native.calls == [] and imported == []


def test_unsupported_platform_and_unknown_probe_do_not_claim_ready(tmp_path):
    manager, _host, _image, downloader, native, _imported = manager_at(tmp_path, host=missing_host(), platform={"os_name": "Linux", "architecture": "x86_64", "os_version": "22.04"})
    task = manager.prepare("linux-key-0001")
    done = wait_terminal(manager, task["task_id"])
    assert done["state"] == "FAILED" and done["error"]["code"] == "SETUP_PLATFORM_UNSUPPORTED"
    assert downloader.calls == 0 and native.calls == []
    manager.probe = lambda: {"docker_accessible": True}
    assert manager.status()["environment_ready"] is None


def test_worker_failure_or_nonboolean_artifact_never_succeeds(tmp_path):
    manager, *_ = manager_at(tmp_path, image={"artifact_ready": 1}, importer=lambda: {"artifact_ready": 1})
    task = manager.prepare("artifact-key-0001")
    done = wait_terminal(manager, task["task_id"])
    assert done["state"] == "FAILED" and done["error"]["code"] == "IMAGE_PREPARATION_UNVERIFIED"
    assert done["error_code"] == "IMAGE_PREPARATION_UNVERIFIED"
    assert done["environment_ready"] is None


@pytest.mark.parametrize("platform,supported", [
    ({"os_name": "Darwin", "architecture": "aarch64", "os_version": "26.0"}, True),
    ({"os_name": "Darwin", "architecture": "aarch64", "os_version": "13.0"}, False),
    ({"os_name": "Darwin", "architecture": "aarch64", "os_version": None}, False),
    ({"os_name": "Darwin", "architecture": "x86_64", "os_version": "26.0"}, False),
    ({"os_name": "Linux", "architecture": "aarch64", "os_version": "22.04"}, False),
])
def test_status_interface_declares_candidate_platform_and_observation(tmp_path, platform, supported):
    manager, *_ = manager_at(tmp_path, platform=platform)
    status = manager.status()
    assert status["platform"] == {"os": platform["os_name"], "architecture": platform["architecture"],
                                  "version": platform["os_version"], "supported": supported}
    assert isinstance(status["observed_at"], str)
    assert status["task"] is None


@pytest.mark.parametrize("available", [None, False, 1])
def test_missing_or_conflicting_docker_evidence_is_unknown(tmp_path, available):
    manager, *_ = manager_at(tmp_path, host=ready_host(docker_available=available))
    assert manager.status()["environment_ready"] is None


def test_single_target_lease_cancellation_and_history_are_persistent(tmp_path):
    entered = threading.Event()
    finish = threading.Event()
    def blocking():
        entered.set()
        finish.wait(2)
        return {"artifact_ready": True}
    manager, _host, _image, _downloader, _native, _imported = manager_at(tmp_path, importer=blocking)
    task = manager.prepare("concurrent-key-0001")
    assert entered.wait(1)
    assert manager.prepare("concurrent-key-0001")["task_id"] == task["task_id"]
    with pytest.raises(SetupError, match="SETUP_BUSY"):
        manager.prepare("concurrent-key-0002")
    second, *_ = manager_at(tmp_path)
    assert second.get(task["task_id"])["state"] == "RUNNING"
    with pytest.raises(SetupError, match="SETUP_BUSY"):
        second.prepare("other-process-key")
    manager.cancel(task["task_id"])
    finish.set()
    cancelled = wait_terminal(manager, task["task_id"], ("CANCELLED",))
    assert cancelled["state"] == "CANCELLED"
    restarted, *_ = manager_at(tmp_path)
    assert restarted.get(task["task_id"])["state"] == "CANCELLED"
    assert restarted.prepare("concurrent-key-0001")["task_id"] == task["task_id"]


def test_restart_running_is_interrupted_without_automatic_actions(tmp_path):
    manager, _host, _image, _downloader, _native, _imported = manager_at(tmp_path, host=missing_host())
    task = manager.prepare("restart-key-0001")
    wait_terminal(manager, task["task_id"])
    path = manager.state_path
    index = json.loads(path.read_text())
    index["tasks"][task["task_id"]]["state"] = "RUNNING"
    path.write_text(json.dumps(index))
    restarted, _, _, new_downloader, new_native, new_imported = manager_at(tmp_path)
    interrupted = restarted.get(task["task_id"])
    assert interrupted["state"] == "INTERRUPTED"
    assert new_downloader.calls == 0 and new_native.calls == [] and new_imported == []
    assert interrupted["environment_ready"] is True  # Current evidence is separate from task history.


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "mode", "state_directory_link"])
def test_private_task_storage_rejects_path_and_permission_attacks(tmp_path, unsafe):
    manager, _host, _image, _downloader, native, imported = manager_at(tmp_path)
    if unsafe == "state_directory_link":
        other = tmp_path / "other"
        other.mkdir()
        manager.state_path.parent.rename(tmp_path / "old")
        manager.state_path.parent.symlink_to(other, target_is_directory=True)
    else:
        path = manager.state_path
        victim = tmp_path / "victim.json"
        if unsafe == "symlink":
            path.rename(victim)
            path.symlink_to(victim)
        elif unsafe == "hardlink":
            os.link(path, victim)
        else:
            path.chmod(0o644)
    with pytest.raises((SetupError, ValueError)):
        manager.prepare("unsafe-key-0001")
    assert native.calls == [] and imported == []


@pytest.mark.parametrize("key", ["x", "../arbitrary", "a" * 129, "x; rm -rf /", "x\nkey"])
def test_bad_request_keys_and_task_ids_rejected(tmp_path, key):
    manager, *_ = manager_at(tmp_path)
    with pytest.raises(SetupError, match="SETUP_REQUEST_INVALID"):
        manager.prepare(key)
    with pytest.raises(SetupError, match="SETUP_TASK_ID_INVALID"):
        manager.get("../../other")


def test_wrong_continue_action_and_unknown_task_do_not_execute(tmp_path):
    manager, _host, _image, downloader, native, _imported = manager_at(tmp_path, host=missing_host())
    task = manager.prepare("action-key-0001")
    wait_terminal(manager, task["task_id"])
    with pytest.raises(SetupError, match="SETUP_ACTION_INVALID"):
        manager.continue_task(task["task_id"], "check_again")
    with pytest.raises(SetupError, match="SETUP_TASK_NOT_FOUND"):
        manager.cancel("b" * 32)
    assert downloader.calls == 0 and native.calls == []


def test_repeated_key_race_rechecks_under_lease(tmp_path, monkeypatch):
    manager, *_ = manager_at(tmp_path)
    existing = manager.prepare("raced-key-0001")
    wait_terminal(manager, existing["task_id"])
    real_read = manager._read
    calls = 0
    def stale_read_once():
        nonlocal calls
        calls += 1
        index = real_read()
        if calls == 1:
            index.tasks.clear()
            index.latest_task_id = None
        return index
    monkeypatch.setattr(manager, "_read", stale_read_once)
    actual = manager.prepare("raced-key-0001")
    assert actual["task_id"] == existing["task_id"]
    assert len(real_read().tasks) == 1


@pytest.mark.parametrize("invalid", [None, [], {"docker_accessible": 1}, {"docker_accessible": True, "endpoint_local": 1}])
def test_malformed_readonly_probe_is_unknown_and_never_raises_success(tmp_path, invalid):
    manager, *_ = manager_at(tmp_path)
    manager.probe = lambda: invalid
    assert manager.status()["environment_ready"] is None


def test_readonly_refresh_preserves_every_task_file(tmp_path):
    manager, *_ = manager_at(tmp_path, host=missing_host())
    task = manager.prepare("refresh-key-0001")
    wait_terminal(manager, task["task_id"])
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in manager.directory.rglob("*") if path.is_file()}
    for _ in range(5):
        manager.status()
        manager.get(task["task_id"])
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in manager.directory.rglob("*") if path.is_file()}
    assert before == after


def test_status_supplies_complete_frontend_contract_even_when_source_blocked(tmp_path):
    manager, *_ = manager_at(tmp_path)
    status = manager.status()
    assert status['evidence'] == {'host': status['host'], 'artifact': status['artifact']}
    assert status['installer']['blocked_reason'] is None
    manager.installer_lock = {}
    status = manager.status()
    assert status['installer']['blocked_reason']
    for key in ['version', 'sha256', 'size_bytes', 'license_url']:
        assert status['installer'][key] is None


@pytest.mark.parametrize('platform', [
    {'os_name': 'Darwin', 'architecture': 'x86_64', 'os_version': '26.0'},
    {'os_name': 'Linux', 'architecture': 'aarch64', 'os_version': '6.8'},
    {'os_name': 'Darwin', 'architecture': 'aarch64', 'os_version': '13.0'},
])
def test_unsupported_platform_cannot_prepare_through_direct_api_even_with_ready_docker(tmp_path, platform):
    manager, _host, _image, _downloader, native, imported = manager_at(tmp_path, platform=platform)
    observed = manager.status()
    assert observed['platform']['supported'] is False
    assert observed['environment_ready'] is not True
    task = manager.prepare('unsupported-platform-key')
    done = wait_terminal(manager, task['task_id'])
    assert done['state'] == 'FAILED'
    assert done['error_code'] == 'SETUP_PLATFORM_UNSUPPORTED'
    assert imported == [] and native.calls == []
