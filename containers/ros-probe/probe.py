"""CPU ROS communication evidence only; no robot or device interface."""
import ipaddress
import json
import math
import os
import re
import socket
import sys
import tempfile
import time
from pathlib import Path

STATUS_PATH = Path("/tmp/d1env-status.json")
TOPIC = "/d1env/test/probe"
MAX_MESSAGE_BYTES = 4096
MAX_SAMPLE_AGE_S = 5.0


def make_dds_profile(peer: str) -> str:
    address = ipaddress.IPv4Address(peer)
    private_networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    if not any(address in ipaddress.IPv4Network(network) for network in private_networks):
        raise ValueError("DDS peer must be an internal IPv4 container address")
    # The fixed profile uses documented Fast DDS UDP/unicast discovery. No host IPC is needed.
    return f'''<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <transport_descriptors>
    <transport_descriptor>
      <transport_id>d1env_udp</transport_id>
      <type>UDPv4</type>
      <maxInitialPeersRange>4</maxInitialPeersRange>
    </transport_descriptor>
  </transport_descriptors>
  <participant profile_name="d1env_probe" is_default_profile="true">
    <rtps>
      <builtin>
        <metatrafficUnicastLocatorList><locator/></metatrafficUnicastLocatorList>
        <initialPeersList><locator><udpv4><address>{address}</address></udpv4></locator></initialPeersList>
      </builtin>
      <userTransports><transport_id>d1env_udp</transport_id></userTransports>
      <useBuiltinTransports>false</useBuiltinTransports>
    </rtps>
  </participant>
</profiles>
'''


def configure_dds(role: str) -> None:
    # Compose owns these two aliases; neither the peer name nor an XML template is user supplied.
    peer_name = {"publisher": "sub", "subscriber": "pub"}[role]
    deadline = time.monotonic() + 5.0
    while True:
        try:
            peer = socket.gethostbyname(peer_name)
            profile = make_dds_profile(peer)
            break
        except socket.gaierror as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"DDS peer {peer_name} is unavailable") from error
            time.sleep(0.1)
    descriptor, path = tempfile.mkstemp(prefix="d1env-dds-", suffix=".xml", dir="/tmp")
    with os.fdopen(descriptor, "w") as handle:
        handle.write(profile)
    os.environ["FASTRTPS_DEFAULT_PROFILES_FILE"] = path
    os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"


def validate_run_id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ValueError("D1ENV_RUN_ID must be a 32-character lowercase job identifier")
    return value


def finite_time(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("invalid Unix timestamp")
    return float(value)


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def encode_sample(run_id: str, sequence: int, sent_at: float) -> str:
    validate_run_id(run_id)
    if type(sequence) is not int or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    timestamp = finite_time(sent_at)
    return json.dumps({"run_id": run_id, "seq": sequence, "sent_at": timestamp},
                      separators=(",", ":"), allow_nan=False)


class SampleTracker:
    def __init__(self, run_id: str):
        self.run_id = validate_run_id(run_id)
        self.sample_count = 0
        self.publisher_id: str | None = None
        self.last_sequence: int | None = None
        self.last_sent_at: float | None = None
        self.last_received_at: float | None = None

    def accept(self, raw: str, received_at: float) -> bool:
        try:
            received = finite_time(received_at)
            if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                return False
            sample = json.loads(raw, object_pairs_hook=unique_object)
            if not isinstance(sample, dict) or set(sample) != {"run_id", "seq", "sent_at"}:
                return False
            if sample["run_id"] != self.run_id:
                return False
            sequence = sample["seq"]
            if type(sequence) is not int or sequence < 1:
                return False
            if self.last_sequence is not None and sequence <= self.last_sequence:
                return False
            sent = finite_time(sample["sent_at"])
            age = received - sent
            if age < 0 or age > MAX_SAMPLE_AGE_S:
                return False
        except (ValueError, TypeError, UnicodeError, OverflowError):
            return False
        self.sample_count += 1
        self.publisher_id = sample["run_id"]
        self.last_sequence = sequence
        self.last_sent_at = sent
        self.last_received_at = received
        return True

    def snapshot(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "publisher_id": self.publisher_id,
            "sample_count": self.sample_count,
            "last_sequence": self.last_sequence,
            "last_sent_at": self.last_sent_at,
            "last_received_at": self.last_received_at,
        }


def write_status(status: dict[str, object], path: Path = STATUS_PATH) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".d1env-status-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(status, handle, separators=(",", ":"), allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_ros(role: str, run_id: str) -> None:
    configure_dds(role)
    # Imports are delayed so pure message contracts can be tested without a host ROS installation.
    import rclpy
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from std_msgs.msg import String

    rclpy.init()
    node = Node(f"d1env_{role}")
    tracker = SampleTracker(run_id)
    if role == "publisher":
        publisher = node.create_publisher(String, TOPIC, 10)
        sequence = 0

        def publish() -> None:
            nonlocal sequence
            sequence += 1
            message = String()
            message.data = encode_sample(run_id, sequence, time.time())
            publisher.publish(message)

        node.create_timer(0.2, publish)
    else:
        write_status(tracker.snapshot())

        def receive(message: String) -> None:
            if tracker.accept(message.data, time.time()):
                write_status(tracker.snapshot())

        node.create_subscription(String, TOPIC, receive, 10)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1 or arguments[0] not in {"publisher", "subscriber", "idle"}:
        print("probe role must be publisher, subscriber or idle", file=sys.stderr)
        return 2
    try:
        run_id = validate_run_id(os.environ.get("D1ENV_RUN_ID", ""))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if arguments[0] == "idle":
        while True:
            time.sleep(60)
    run_ros(arguments[0], run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
