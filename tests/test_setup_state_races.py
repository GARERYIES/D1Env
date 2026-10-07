"""Deterministic owned atomic JSON replacement and unchanged unsafe-file rejection."""

import os
import stat
import threading
from pathlib import Path

import pytest
from test_setup_manager import manager_at, missing_host, wait_terminal

from d1env.setup import manager as manager_module
from d1env.setup.models import SetupError


def waiting_manager(tmp_path):
    manager, *_ = manager_at(tmp_path, host=missing_host())
    task = manager.prepare("atomic-read-key-0001")
    wait_terminal(manager, task["task_id"])
    return manager, task["task_id"]


def test_owned_atomic_replace_during_open_rereads_the_new_private_inode(tmp_path, monkeypatch):
    manager, task_id = waiting_manager(tmp_path)
    opened = threading.Event()
    replaced = threading.Event()
    actual_validate = manager_module.validate_descriptor
    paused = False
    observations = []
    errors = []
    results = []

    def pause_old_descriptor(descriptor):
        nonlocal paused
        if threading.current_thread().name == "setup-race-reader" and not paused:
            paused = True
            opened.set()
            assert replaced.wait(2)
            observations.append(os.fstat(descriptor).st_nlink)
        actual_validate(descriptor)

    monkeypatch.setattr(manager_module, "validate_descriptor", pause_old_descriptor)

    def read():
        try:
            results.append(manager.get(task_id))
        except (ValueError, OSError) as exc:
            errors.append(exc)

    reader = threading.Thread(target=read, name="setup-race-reader", daemon=True)
    reader.start()
    assert opened.wait(2)
    try:
        manager._update(task_id, "WAITING_USER", "license", "owned atomic state update",
                        user_action="accept_license")
    finally:
        replaced.set()
    reader.join(2)
    assert not reader.is_alive()
    assert observations == [0]
    assert errors == []
    assert results[0]["message"] == "owned atomic state update"
    assert results[0]["state"] == "WAITING_USER"
    assert results[0]["environment_ready"] is False


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "public_mode", "missing", "foreign_owner"])
def test_unlinked_reader_never_retries_an_unsafe_replacement(tmp_path, monkeypatch, unsafe):
    manager, task_id = waiting_manager(tmp_path)
    original = manager.state_path.read_bytes()
    actual_validate = manager_module.validate_descriptor
    actual_lstat = Path.lstat
    replacements = 0

    def replace_before_validate(descriptor):
        nonlocal replacements
        if replacements == 0:
            replacements += 1
            manager.state_path.unlink()
            if unsafe != "missing":
                replacement = tmp_path / "replacement.json"
                replacement.write_bytes(original)
                replacement.chmod(0o600)
                if unsafe == "symlink":
                    manager.state_path.symlink_to(replacement)
                elif unsafe == "hardlink":
                    os.link(replacement, manager.state_path)
                else:
                    replacement.rename(manager.state_path)
                    if unsafe == "public_mode":
                        manager.state_path.chmod(0o644)
        actual_validate(descriptor)

    def with_foreign_owner(path, *args, **kwargs):
        observed = actual_lstat(path, *args, **kwargs)
        if replacements and unsafe == "foreign_owner" and path == manager.state_path:
            values = list(observed)
            values[4] = os.getuid() + 1
            return os.stat_result(values)
        return observed

    monkeypatch.setattr(manager_module, "validate_descriptor", replace_before_validate)
    monkeypatch.setattr(Path, "lstat", with_foreign_owner)
    with pytest.raises(SetupError, match="SETUP_STATE_INVALID"):
        manager.get(task_id)
    assert replacements == 1


def test_repeated_valid_atomic_replacements_stop_after_three_attempts(tmp_path, monkeypatch):
    manager, task_id = waiting_manager(tmp_path)
    index = manager._read()
    actual_validate = manager_module.validate_descriptor
    replacements = 0

    def continually_replace_current_inode(descriptor):
        nonlocal replacements
        observed = os.fstat(descriptor)
        current = manager.state_path.lstat()
        if (observed.st_dev, observed.st_ino) == (current.st_dev, current.st_ino):
            replacements += 1
            manager._write(index)
        actual_validate(descriptor)

    monkeypatch.setattr(manager_module, "validate_descriptor", continually_replace_current_inode)
    with pytest.raises(SetupError, match="SETUP_STATE_INVALID") as failed:
        manager.get(task_id)
    assert replacements == 3
    assert failed.value.evidence == {"reason": "atomic_state_replacements_exhausted", "max_attempts": 3}
    assert index.tasks[task_id].state == "WAITING_USER"


def test_unlinked_descriptor_with_same_current_identity_is_rejected(tmp_path, monkeypatch):
    manager, task_id = waiting_manager(tmp_path)
    actual_fstat = os.fstat

    def impossible_unlinked_same_inode(descriptor):
        observed = actual_fstat(descriptor)
        if stat.S_ISREG(observed.st_mode):
            values = list(observed)
            values[3] = 0
            return os.stat_result(values)
        return observed

    monkeypatch.setattr(os, "fstat", impossible_unlinked_same_inode)
    with pytest.raises(SetupError, match="SETUP_STATE_INVALID"):
        manager.get(task_id)


@pytest.mark.parametrize("unsafe", ["mode", "owner", "hardlink"])
def test_unsafe_old_descriptor_is_rejected_even_if_current_replacement_is_private(tmp_path, monkeypatch, unsafe):
    manager, task_id = waiting_manager(tmp_path)
    index = manager._read()
    actual_validate = manager_module.validate_descriptor
    actual_fstat = os.fstat
    old_identity = None
    replacements = 0

    def replace_before_validate(descriptor):
        nonlocal replacements, old_identity
        observed = actual_fstat(descriptor)
        if replacements == 0:
            old_identity = (observed.st_dev, observed.st_ino)
            replacements += 1
            manager._write(index)
        actual_validate(descriptor)

    def unsafe_old_fstat(descriptor):
        observed = actual_fstat(descriptor)
        if old_identity == (observed.st_dev, observed.st_ino):
            values = list(observed)
            if unsafe == "mode":
                values[0] |= 0o004
            elif unsafe == "owner":
                values[4] = os.getuid() + 1
            else:
                values[3] = 2
            return os.stat_result(values)
        return observed

    monkeypatch.setattr(manager_module, "validate_descriptor", replace_before_validate)
    monkeypatch.setattr(os, "fstat", unsafe_old_fstat)
    with pytest.raises(SetupError, match="SETUP_STATE_INVALID"):
        manager.get(task_id)
    assert replacements == 1
