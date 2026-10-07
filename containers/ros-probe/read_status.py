"""Fixed, bounded JSON reader used by the deployment executor; no ROS import."""
import json
import math
import os
import re
import sys
from pathlib import Path

STATUS_PATH = Path("/tmp/d1env-status.json")
MAX_STATUS_BYTES = 32768


def read_status(path: Path = STATUS_PATH, run_id: str | None = None) -> dict[str, object]:
    expected = os.environ.get("D1ENV_RUN_ID", "") if run_id is None else run_id
    if re.fullmatch(r"[0-9a-f]{32}", expected) is None:
        raise ValueError("invalid run identifier")
    empty = {"run_id": expected, "publisher_id": None, "sample_count": 0,
             "last_sequence": None, "last_sent_at": None, "last_received_at": None}
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_STATUS_BYTES + 1)
    except FileNotFoundError:
        return empty
    if len(raw) > MAX_STATUS_BYTES:
        raise ValueError("status exceeds bounded read")
    try:
        status = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ValueError("invalid status JSON") from error
    if not isinstance(status, dict) or set(status) != set(empty) or status["run_id"] != expected:
        raise ValueError("invalid status identity or fields")
    count = status["sample_count"]
    if type(count) is not int or count < 0:
        raise ValueError("invalid sample count")
    if count == 0:
        if status != empty:
            raise ValueError("absent samples must remain null")
    else:
        sequence = status["last_sequence"]
        if status["publisher_id"] != expected or type(sequence) is not int or sequence < count:
            raise ValueError("invalid publisher identity or sequence")
        for name in ("last_sent_at", "last_received_at"):
            timestamp = status[name]
            if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp <= 0:
                raise ValueError("invalid status timestamp")
    return status


def main() -> int:
    if len(sys.argv) != 1:
        print("status reader does not accept arguments", file=sys.stderr)
        return 2
    try:
        status = read_status()
    except (ValueError, OSError) as error:
        print(json.dumps({"error": "STATUS_INVALID", "reason": str(error)}))
        return 1
    print(json.dumps(status, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
