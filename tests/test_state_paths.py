import os
import stat
from pathlib import Path

import pytest

from d1env.jobs.engine import JobEngine
from d1env.jobs.store import Store


def test_sqlite_symlink_cannot_overwrite_existing_user_file(tmp_path):
    user_file = tmp_path / "my-map.bin"
    user_file.write_bytes(b"existing map data")
    path = tmp_path / "jobs.sqlite"
    path.symlink_to(user_file)
    with pytest.raises(ValueError, match="STATE_FILE_UNSAFE"):
        Store(path)
    assert user_file.read_bytes() == b"existing map data"


def test_sqlite_hardlink_cannot_modify_existing_user_database(tmp_path):
    import os
    original = tmp_path / "owned.sqlite"
    Store(original)
    before = original.read_bytes()
    path = tmp_path / "jobs.sqlite"
    os.link(original, path)
    with pytest.raises(ValueError, match="STATE_FILE_UNSAFE"):
        Store(path)
    assert original.read_bytes() == before


def test_resource_directory_link_is_rejected_before_writing(tmp_path):
    user_directory = tmp_path / "maps"
    user_directory.mkdir()
    path = tmp_path / "resources"
    path.symlink_to(user_directory, target_is_directory=True)
    with pytest.raises(ValueError, match="RESOURCE_DIRECTORY_UNSAFE"):
        JobEngine(Store(tmp_path / "jobs.sqlite"), path)
    assert list(user_directory.iterdir()) == []


def _metadata(original, *, nlink=1, mode=None):
    values = list(original)
    values[3] = nlink
    if mode is not None:
        values[0] = mode
    return os.stat_result(values)


def test_deleted_sqlite_auxiliary_metadata_is_rechecked_once(tmp_path, monkeypatch):
    store = Store(tmp_path / "jobs.sqlite")
    regular = store.path.lstat()
    original = Path.lstat
    wal = Path(str(store.path) + "-wal")
    calls = []
    def during_unlink(path, *args, **kwargs):
        if path == wal:
            calls.append(path.name)
            if len(calls) == 1:
                return _metadata(regular, nlink=0)
            raise FileNotFoundError("SQLite auxiliary file was deleted")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", during_unlink)
    assert store.list_jobs() == []
    assert calls == ["jobs.sqlite-wal", "jobs.sqlite-wal"]


@pytest.mark.parametrize("replacement", ["regular", "hardlink", "symlink", "group_write"])
def test_sqlite_auxiliary_replacement_keeps_all_ownership_checks(tmp_path, monkeypatch, replacement):
    store = Store(tmp_path / "jobs.sqlite")
    regular = store.path.lstat()
    original = Path.lstat
    shm = Path(str(store.path) + "-shm")
    calls = []
    def during_replacement(path, *args, **kwargs):
        if path == shm:
            calls.append(path.name)
            if len(calls) == 1:
                return _metadata(regular, nlink=0)
            return _metadata(regular, nlink=2 if replacement == "hardlink" else 1,
                mode=stat.S_IFLNK | 0o777 if replacement == "symlink" else
                stat.S_IFREG | 0o664 if replacement == "group_write" else regular.st_mode)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", during_replacement)
    if replacement == "regular":
        assert store.list_jobs() == []
    else:
        with pytest.raises(ValueError, match="STATE_FILE_UNSAFE"):
            store.list_jobs()
    assert len(calls) == 2
