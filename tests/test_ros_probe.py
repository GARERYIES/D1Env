import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "containers/ros-probe"
RUN_ID = "1" * 32


def load_source(name):
    path = SOURCE / f"{name}.py"
    assert path.is_file(), f"Missing real ROS probe implementation: {path}"
    spec = importlib.util.spec_from_file_location(f"d1env_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_counts_only_fresh_ordered_matching_ros_payloads():
    tracker = load_source("probe").SampleTracker(RUN_ID)
    assert tracker.snapshot() == {
        "run_id": RUN_ID, "publisher_id": None, "sample_count": 0,
        "last_sequence": None, "last_sent_at": None, "last_received_at": None,
    }
    for sequence in (1, 2, 3):
        assert tracker.accept(json.dumps({"run_id": RUN_ID, "seq": sequence, "sent_at": 100.0}), 101.0)
    assert not tracker.accept(json.dumps({"run_id": RUN_ID, "seq": 3, "sent_at": 101.0}), 102.0)
    assert not tracker.accept(json.dumps({"run_id": "2" * 32, "seq": 4, "sent_at": 101.0}), 102.0)
    assert tracker.snapshot() == {
        "run_id": RUN_ID, "publisher_id": RUN_ID, "sample_count": 3,
        "last_sequence": 3, "last_sent_at": 100.0, "last_received_at": 101.0,
    }


@pytest.mark.parametrize("payload", [
    "null", "[]", "{}", "not JSON",
    json.dumps({"run_id": RUN_ID, "seq": True, "sent_at": 100.0}),
    json.dumps({"run_id": RUN_ID, "seq": 0, "sent_at": 100.0}),
    json.dumps({"run_id": RUN_ID, "seq": 1.0, "sent_at": 100.0}),
    json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": True}),
    json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": float("nan")}),
    json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": float("inf")}),
    json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": 100.0, "command": "anything"}),
    '{"run_id":"' + RUN_ID + '","seq":1,"seq":2,"sent_at":100}',
    "中" * 2048,
], ids=["null", "array", "empty", "invalid-json", "bool-seq", "zero-seq", "float-seq",
        "bool-time", "nan-time", "infinite-time", "extra-key", "duplicate-key", "oversized-utf8"])
def test_malformed_ros_payload_cannot_count_as_a_sample(payload):
    tracker = load_source("probe").SampleTracker(RUN_ID)
    assert not tracker.accept(payload, 101.0)
    assert tracker.snapshot()["sample_count"] == 0
    assert tracker.snapshot()["publisher_id"] is None


@pytest.mark.parametrize("sent_at", [95.9, 101.1])
def test_stale_and_future_ros_samples_are_not_accepted(sent_at):
    tracker = load_source("probe").SampleTracker(RUN_ID)
    assert not tracker.accept(json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": sent_at}), 101.0)
    assert tracker.snapshot()["last_received_at"] is None


@pytest.mark.parametrize("received_at", [float("nan"), float("inf"), True, 0])
def test_invalid_receive_time_cannot_refresh_status(received_at):
    tracker = load_source("probe").SampleTracker(RUN_ID)
    assert not tracker.accept(json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": 100.0}), received_at)
    assert tracker.snapshot()["sample_count"] == 0


@pytest.mark.parametrize("run_id", ["", "../escape", "A" * 32, "0" * 31, "g" * 32])
def test_run_identifier_rejects_paths_and_non_job_values(run_id):
    with pytest.raises(ValueError):
        load_source("probe").SampleTracker(run_id)


def test_published_json_carries_real_identity_sequence_and_time():
    raw = load_source("probe").encode_sample(RUN_ID, 1, 100.25)
    assert json.loads(raw) == {"run_id": RUN_ID, "seq": 1, "sent_at": 100.25}


def test_atomic_status_roundtrip_does_not_create_readiness_without_samples(tmp_path):
    probe = load_source("probe")
    reader = load_source("read_status")
    path = tmp_path / "status.json"
    tracker = probe.SampleTracker(RUN_ID)
    probe.write_status(tracker.snapshot(), path)
    assert reader.read_status(path, RUN_ID) == {
        "run_id": RUN_ID, "publisher_id": None, "sample_count": 0,
        "last_sequence": None, "last_sent_at": None, "last_received_at": None,
    }
    assert tracker.accept(json.dumps({"run_id": RUN_ID, "seq": 1, "sent_at": 100.0}), 101.0)
    probe.write_status(tracker.snapshot(), path)
    assert reader.read_status(path, RUN_ID)["sample_count"] == 1
    assert list(tmp_path.iterdir()) == [path]


def test_missing_status_file_reports_absent_samples(tmp_path):
    assert load_source("read_status").read_status(tmp_path / "missing.json", RUN_ID) == {
        "run_id": RUN_ID, "publisher_id": None, "sample_count": 0,
        "last_sequence": None, "last_sent_at": None, "last_received_at": None,
    }


@pytest.mark.parametrize("contents", ["not JSON", "[]", '{"sample_count":3}', "x" * 32769],
                         ids=["invalid-json", "array", "incomplete", "oversized"])
def test_status_reader_rejects_invalid_or_oversized_state(tmp_path, contents):
    path = tmp_path / "status.json"
    path.write_text(contents)
    with pytest.raises(ValueError):
        load_source("read_status").read_status(path, RUN_ID)


@pytest.mark.parametrize("args", [[], ["shell"], ["publisher", "extra"]])
def test_entry_role_rejects_arbitrary_or_extra_commands(args):
    path = SOURCE / "probe.py"
    assert path.is_file(), "Missing fixed-role probe entrypoint"
    result = subprocess.run([sys.executable, str(path), *args],
                            env={**os.environ, "D1ENV_RUN_ID": RUN_ID}, capture_output=True,
                            text=True, timeout=5, check=False)
    assert result.returncode == 2


def test_dds_profile_uses_private_unicast_peer_and_udp_without_host_shared_memory():
    profile = load_source("probe").make_dds_profile("172.21.0.3")
    tree = ElementTree.fromstring(profile)
    ns = {"dds": "http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles"}
    assert tree.findtext(".//dds:transport_descriptor/dds:type", namespaces=ns) == "UDPv4"
    assert tree.findtext(".//dds:useBuiltinTransports", namespaces=ns) == "false"
    assert tree.findtext(".//dds:initialPeersList//dds:address", namespaces=ns) == "172.21.0.3"
    assert tree.find(".//dds:metatrafficUnicastLocatorList", ns) is not None


@pytest.mark.parametrize("peer", ["8.8.8.8", "127.0.0.1", "0.0.0.0", "239.255.0.1", "pub", "<unsafe>"])
def test_dds_profile_rejects_external_or_arbitrary_peer_configuration(peer):
    with pytest.raises(ValueError):
        load_source("probe").make_dds_profile(peer)
