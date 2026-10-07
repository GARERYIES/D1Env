import hashlib
import io
import os
import threading

import pytest

from d1env.setup.download import InstallerDownloader
from d1env.setup.models import SetupError, validate_installer_lock


def lock_for(data=b"official test bytes"):
    return {
        "schema_version": 1, "kind": "d1env_docker_desktop_installer",
        "retrieval_status": "verified", "platform": "macos", "architecture": "aarch64",
        "version": "4.80.0", "build": "232116",
        "url": "https://desktop.docker.com/mac/main/arm64/232116/Docker.dmg",
        "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
        "team_id": "9BNSXJN65R", "bundle_id": "com.docker.docker",
        "minimum_macos": "14.0",
        "license_url": "https://www.docker.com/legal/docker-subscription-service-agreement/",
    }


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url
        self.status = 200
        self.headers = {"Content-Length": str(len(data))}

    def geturl(self):
        return self.url


def test_download_streams_verifies_and_reuses_only_complete_cache(tmp_path):
    data = b"official test bytes"
    calls = []
    lock = lock_for(data)
    downloader = InstallerDownloader(
        tmp_path, opener=lambda url: (calls.append(url) or Response(data, url)),
        free_space=lambda path: 1024**3,
    )
    progress = []
    result = downloader.fetch(lock, threading.Event(), lambda done, total: progress.append(done))
    assert result.read_bytes() == data
    assert result.stat().st_mode & 0o777 == 0o600
    assert progress[-1] == len(data)
    assert downloader.fetch(lock, threading.Event(), lambda *args: None) == result
    assert len(calls) == 1
    result.write_bytes(b"x" * len(data))
    with pytest.raises(SetupError, match="INSTALLER_HASH_MISMATCH"):
        downloader.fetch(lock, threading.Event(), lambda *args: None)
    assert len(calls) == 1
    assert not result.exists()  # Only the invalid private cache is invalidated.
    assert downloader.fetch(lock, threading.Event(), lambda *args: None).read_bytes() == data
    assert len(calls) == 2


@pytest.mark.parametrize("patch", [
    {"url": "http://desktop.docker.com/mac/main/arm64/232116/Docker.dmg"},
    {"url": "https://evil.example/Docker.dmg"},
    {"url": "https://desktop.docker.com@evil.example/Docker.dmg"},
    {"url": "https://desktop.docker.com/mac/main/arm64/232116/Docker.dmg?command=evil"},
    {"team_id": "ANYTHING"}, {"bundle_id": "malicious"}, {"size_bytes": True},
    {"sha256": "0" * 64}, {"retrieval_status": "blocked"},
])
def test_untrusted_installer_metadata_rejected_before_network(patch):
    with pytest.raises(SetupError, match="INSTALLER_SOURCE_BLOCKED"):
        validate_installer_lock({**lock_for(), **patch})


@pytest.mark.parametrize("data,code", [(b"short", "INSTALLER_SIZE_MISMATCH"),
                                     (b"x" * 100, "INSTALLER_SIZE_MISMATCH"),
                                     (b"unofficial bad bytes", "INSTALLER_HASH_MISMATCH")])
def test_wrong_download_never_becomes_verified_cache(tmp_path, data, code):
    lock = lock_for()
    # Equal length makes the last case an actual digest failure.
    if code == "INSTALLER_HASH_MISMATCH":
        data = b"x" * lock["size_bytes"]
    downloader = InstallerDownloader(tmp_path, opener=lambda url: Response(data, url),
                                     free_space=lambda path: 1024**3)
    with pytest.raises(SetupError, match=code):
        downloader.fetch(lock, threading.Event(), lambda *args: None)
    assert not (tmp_path / (lock["sha256"] + ".dmg")).exists()


def test_redirect_cancel_low_space_and_partial_are_safe(tmp_path):
    lock = lock_for()
    partial = tmp_path / (lock["sha256"] + ".part")
    partial.write_bytes(b"incomplete")
    partial.chmod(0o600)
    downloader = InstallerDownloader(tmp_path, opener=lambda url: Response(b"official test bytes", url),
                                     free_space=lambda path: 1024**3)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(SetupError, match="SETUP_CANCELLED"):
        downloader.fetch(lock, cancel, lambda *args: None)
    cancel.clear()
    bad = InstallerDownloader(tmp_path, opener=lambda url: Response(b"official test bytes", "https://evil.example/a"),
                              free_space=lambda path: 1024**3)
    with pytest.raises(SetupError, match="INSTALLER_REDIRECT_REJECTED"):
        bad.fetch(lock, cancel, lambda *args: None)
    low = InstallerDownloader(tmp_path, free_space=lambda path: 0)
    with pytest.raises(SetupError, match="INSTALLER_DISK_SPACE"):
        low.fetch(lock, cancel, lambda *args: None)
    assert downloader.fetch(lock, cancel, lambda *args: None).read_bytes() == b"official test bytes"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public"])
def test_cache_file_permission_and_link_attacks(tmp_path, kind):
    lock = lock_for()
    destination = tmp_path / (lock["sha256"] + ".dmg")
    victim = tmp_path / "victim"
    victim.write_bytes(b"official test bytes")
    victim.chmod(0o600)
    if kind == "symlink":
        destination.symlink_to(victim)
    elif kind == "hardlink":
        os.link(victim, destination)
    else:
        destination.write_bytes(b"official test bytes")
        destination.chmod(0o644)
    with pytest.raises(SetupError, match="SETUP_FILE_UNSAFE"):
        InstallerDownloader(tmp_path).fetch(lock, threading.Event(), lambda *args: None)
    assert victim.read_bytes() == b"official test bytes"


def test_cancellation_between_chunks_never_promotes_partial_then_explicit_retry(tmp_path):
    data = b"a" * (1024**2 + 64)
    lock = lock_for(data)
    cancel = threading.Event()
    class CancellingResponse(Response):
        def read(self, count=-1):
            chunk = super().read(count)
            cancel.set()
            return chunk
    downloader = InstallerDownloader(tmp_path, opener=lambda url: CancellingResponse(data, url),
                                     free_space=lambda path: 2 * 1024**3)
    with pytest.raises(SetupError, match="SETUP_CANCELLED"):
        downloader.fetch(lock, cancel, lambda *args: None)
    assert not (tmp_path / (lock["sha256"] + ".dmg")).exists()
    assert (tmp_path / (lock["sha256"] + ".part")).stat().st_size == 1024**2
    cancel.clear()
    downloader.opener = lambda url: Response(data, url)
    assert downloader.fetch(lock, cancel, lambda *args: None).read_bytes() == data
