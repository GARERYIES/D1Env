from d1env.models import CheckResult, JobEvent, JobSnapshot, utcnow
from d1env.reports import build_report, markdown_report


def sample():
    now = utcnow()
    job = JobSnapshot(job_id="job-1",plan_id="plan-1",target_id="local",mode="mock",
                      state="FAILED",verified_scope="mock",created_at=now,updated_at=now)
    event = JobEvent(job_id="job-1",seq=1,timestamp=now,event_type="failure",mode="mock",origin="mock",
                     message="MOCK故障 permission denied; device 192.168.1.10 serial=ROBOT123",
                     evidence={"nested":[{"Authorization":"Bearer SECRET", "session":"SESSION", "api_key":"APISECRET"}],
                               "csrf_token":"CSRFSECRET", "serial_number":"ROBOT123", "ip":"192.168.1.10"})
    check = CheckResult(code="ROBOT",status="UNKNOWN",reason="not connected",remediation="M4",
                        origin="local_probe",observed_at=now,evidence={"battery":None})
    return job,[check],[event]


def test_credentials_are_recursively_redacted():
    report = build_report(*sample())
    text = report.model_dump_json()
    for secret in ["SECRET", "SESSION", "APISECRET", "CSRFSECRET"]:
        assert secret not in text
    assert "permission denied" in text
    assert "UNKNOWN" in text and "local_probe" in text
    assert report.redactions


def test_identifier_masking_is_optional_and_preserves_scope():
    report = build_report(*sample(), mask_identifiers=True)
    assert "192.168.1.10" not in report.model_dump_json()
    assert "ROBOT123" not in report.model_dump_json()
    unmasked = build_report(*sample(), mask_identifiers=False)
    assert "192.168.1.10" in unmasked.model_dump_json()
    assert unmasked.mode == "mock" and unmasked.verified_scope == "mock"
    assert "M3" in " ".join(report.unverified_items)
    text = markdown_report(report)
    assert "MOCK" in text and "未部署真机" in text
    assert "FAILED" in text and "UNKNOWN" in text


def test_pem_and_bearer_in_messages_never_exported():
    job,checks,events = sample()
    events[0].message = "error Bearer abcdef12345 -----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
    text = build_report(job,checks,events).model_dump_json()
    assert "abcdef12345" not in text and "secret" not in text


def test_application_session_cookie_and_header_names_are_redacted():
    from d1env.reports import redact
    data = {"nested":[{"d1env_session":"COOKIESAMPLE", "Set-Cookie":"d1env_session=HEADERSAMPLE; HttpOnly",
                       "X-CSRF-Token":"CSRFHEADERSAMPLE", "log":"d1env_session=LOGSAMPLE"}]}
    text = str(redact(data, True, set()))
    for sample in ["COOKIESAMPLE","HEADERSAMPLE","CSRFHEADERSAMPLE","LOGSAMPLE"]:
        assert sample not in text


def test_ipv6_text_mask_covers_brackets_zone_and_mapped_addresses():
    from d1env.reports import redact
    text = "MOCK evidence [2001:db8::1], ip=fe80::abcd%en0 mapped=::ffff:192.0.2.1; ip:2001:db8::2 peer:2001:db8::3 loopback:::1; permission denied. version=1.2.3"
    masked = redact(text, True, set())
    assert isinstance(masked, str)
    for address in ["2001:db8::1", "2001:db8::2", "2001:db8::3", "fe80::abcd", "en0", "::ffff:", "192.0.2.1", "::1"]:
        assert address not in masked
    assert "permission denied" in masked and "version=1.2.3" in masked
    assert "ip:[IP]" in masked and "peer:[IP]" in masked and "loopback:[IP]" in masked
    assert redact(text, False, set()) == text
