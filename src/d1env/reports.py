import ipaddress
import json
import re
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from .models import CheckResult, DiagnosticReport, JobEvent, JobSnapshot

SENSITIVE_KEYS = {"authorization", "password", "passwd", "token", "accesstoken", "refreshtoken",
                  "apikey", "secret", "privatekey", "session", "sessionid", "cookie", "csrftoken",
                  "bootstrap", "bootstraptoken", "credentials", "d1envsession", "setcookie",
                  "xcsrftoken"}
IDENTIFIER_KEYS = {"ip", "ipaddress", "serial", "serialnumber", "robotserial"}


def mask_ipv6(match: re.Match[str]) -> str:
    candidate = match.group(0)
    address = candidate.rstrip(".")
    try:
        ipaddress.IPv6Address(address)
    except ipaddress.AddressValueError:
        return candidate
    return "[IP]" + candidate[len(address):]


def redact(value: JsonValue, mask_identifiers: bool, redactions: set[str]) -> JsonValue:
    if isinstance(value, dict):
        output: dict[str, JsonValue] = {}
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in SENSITIVE_KEYS or any(normalized.endswith(k) for k in ["password", "token", "secret", "apikey"]):
                output[key] = "[REDACTED]"
                redactions.add("credential fields")
            elif mask_identifiers and normalized in IDENTIFIER_KEYS:
                output[key] = "[IDENTIFIER]"
                redactions.add("identifiers")
            else:
                output[key] = redact(child, mask_identifiers, redactions)
        return output
    if isinstance(value, list):
        return [redact(child, mask_identifiers, redactions) for child in value]
    if isinstance(value, str):
        result = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[PRIVATE_KEY]", value, flags=re.DOTALL)
        result = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "[AUTHORIZATION]", result)
        result = re.sub(r"(?i)\b(?:password|token|api[_-]?key|secret|session|d1env_session|csrf[_-]?token)\s*[=:]\s*[^\s,;]+", "[CREDENTIAL]", result)
        result = re.sub(r"/(?:Users|home)/[^\s\"']+", "[LOCAL_PATH]", result)
        if mask_identifiers:
            result = re.sub(r"(?<![0-9a-zA-Z])[0-9a-fA-F:.]+(?:%[0-9a-zA-Z_.-]+)?", mask_ipv6, result)
            result = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP]", result)
            result = re.sub(r"(?i)\bserial(?:_number)?\s*[=:]\s*[^\s,;]+", "[SERIAL]", result)
        if result != value:
            redactions.add("sensitive text")
        return result
    return value


def build_report(job: JobSnapshot, checks: list[CheckResult], events: list[JobEvent],
                 *, mask_identifiers: bool = True,
                 source_locks: dict[str, JsonValue] | None = None) -> DiagnosticReport:
    if source_locks is None:
        source_file = Path(__file__).resolve().parents[2] / "docs/research/UPSTREAM_LOCK.json"
        source_locks = json.loads(source_file.read_text()) if source_file.exists() else {"retrieval_status": "blocked", "reason": "source lock unavailable"}
    redactions: set[str] = set()
    return DiagnosticReport(
        mode=job.mode, verified_scope=job.verified_scope,
        job=cast(dict[str, JsonValue], redact(job.model_dump(mode="json"), mask_identifiers, redactions)),
        checks=[cast(dict[str, JsonValue], redact(c.model_dump(mode="json"), mask_identifiers, redactions)) for c in checks],
        events=[cast(dict[str, JsonValue], redact(e.model_dump(mode="json"), mask_identifiers, redactions)) for e in events],
        source_locks=cast(dict[str, JsonValue], redact(source_locks, mask_identifiers, redactions)),
        unverified_items=["M3 全新 Ubuntu 22.04 x86_64 安装与桌面入口未验证",
                          *( ["该作业仅为 MOCK，未部署真实容器"] if job.mode == "mock" else
                             ["该作业仅验证 Docker/ROS 软件测试，不能证明 D1 功能或安装包已完成"]),
                          "M4 厂商 SDK 与真机遥测未验证",
                          "M5 传感器、建图与导航未验证", "M6 运动与硬件停止行为未验证"],
        redactions=sorted(redactions),
    )


def markdown_report(report: DiagnosticReport) -> str:
    body = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    # Any hostile fence remains inside a four-backtick block after escaping backticks.
    body = body.replace("`", "\\u0060")
    label = "MOCK" if report.mode == "mock" else "真实软件测试"
    description = "演示软件流程证据，未部署真机。" if report.mode == "mock" else "Docker/ROS 软件通信测试证据，未连接真机。"
    return (f"# D1Env 诊断报告 · {label}\n\n{description}"
            f"\n\n模式：{report.mode}；验证范围：{report.verified_scope}\n\n"
            "真实主机观测的来源为 local_probe；它不提高作业验证范围。\n\n"
            f"```json\n{body}\n```\n")
