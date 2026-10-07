import threading

import pytest
from test_setup_download import Response, lock_for

from d1env.setup import download
from d1env.setup.download import InstallerDownloader
from d1env.setup.models import SetupError


def test_official_http_adapter_uses_single_receive_read1(monkeypatch):
    class SlowHTTP:
        status = 200
        def __init__(self):
            self.read1_calls = []
            self.closed = False
        def geturl(self):
            return lock_for()["url"]
        def read(self, count):
            raise AssertionError("HTTPResponse.read can fill a megabyte indefinitely")
        def read1(self, count):
            self.read1_calls.append(count)
            return b"one received fragment"
        def close(self):
            self.closed = True
    response = SlowHTTP()
    class Opener:
        def open(self, url, timeout):
            assert timeout == 15
            return response
    monkeypatch.setattr(download.urllib.request, "build_opener", lambda *handlers: Opener())
    adapter = download._open_official(lock_for()["url"])
    assert adapter.read(1024**2) == b"one received fragment"
    assert response.read1_calls == [1024**2]
    adapter.close()
    assert response.closed is True


@pytest.mark.parametrize("timeout", [0, -1, 3600.01, float("inf"), float("nan"), True])
def test_download_deadline_is_constructor_bounded_and_not_http_configurable(tmp_path, timeout):
    with pytest.raises(ValueError, match="bounded download deadline"):
        InstallerDownloader(tmp_path, download_timeout_s=timeout)


def test_expired_overall_deadline_does_not_promote_partial_even_if_fragments_arrive(tmp_path):
    data = b"official test bytes"
    lock = lock_for(data)
    now = [0.0]
    class SlowFragments(Response):
        def read(self, count=-1):
            now[0] += 2
            return super().read(1)
    downloader = InstallerDownloader(tmp_path, opener=lambda url: SlowFragments(data, url),
                                     free_space=lambda path: 1024**3, clock=lambda: now[0],
                                     download_timeout_s=5)
    with pytest.raises(SetupError, match="INSTALLER_DOWNLOAD_TIMEOUT") as failed:
        downloader.fetch(lock, threading.Event(), lambda *args: None)
    assert failed.value.evidence["timeout_seconds"] == 5
    assert not (tmp_path / (lock["sha256"] + ".dmg")).exists()
    assert (tmp_path / (lock["sha256"] + ".part")).read_bytes() == data[:2]


def test_progress_persistence_is_throttled_for_byte_drip_but_reports_completion(tmp_path):
    data = b"a" * 100
    lock = lock_for(data)
    now = [0.0]
    class TinyFragments(Response):
        def read(self, count=-1):
            now[0] += 0.01
            return super().read(1)
    progress = []
    downloader = InstallerDownloader(tmp_path, opener=lambda url: TinyFragments(data, url),
                                     free_space=lambda path: 1024**3, clock=lambda: now[0])
    path = downloader.fetch(lock, threading.Event(), lambda done, total: progress.append((done, total)))
    assert path.read_bytes() == data
    assert 3 <= len(progress) <= 5
    assert progress[-1] == (100, 100)


def test_progress_reports_each_megabyte_without_waiting_for_clock(tmp_path):
    data = b"a" * (2 * 1024**2 + 20)
    lock = lock_for(data)
    progress = []
    downloader = InstallerDownloader(tmp_path, opener=lambda url: Response(data, url),
                                     free_space=lambda path: 2 * 1024**3, clock=lambda: 0.0)
    downloader.fetch(lock, threading.Event(), lambda done, total: progress.append(done))
    assert progress == [1024**2, 2 * 1024**2, len(data)]
