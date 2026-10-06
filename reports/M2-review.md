# D1Env Foundation fresh implementation review

Review date: 2026-10-06. Reviewer: actual upstream_audit subagent. Read-only source/test review; no code edits, commits, SDK calls, robot connections, container operations, or nested agents.

Scope: adopted AGENTS.md, design and Foundation Task 0–7; ACCEPTANCE A01–A12. Initial review began on HEAD `6cd82ef` with backend/UI/report work still changing. Final closure reviewed at `0b08620`, including the latest IPv6 delimiter and interrupted-plan retry repairs. Findings below describe the code observed at reproduction time; all reproduced findings are repaired with explicit closure evidence. No remaining actionable finding was identified in this M0–M2 review.

## Reproduced findings

### P2, repaired: Report redaction missed the application's own session cookie names

Observed location: `src/d1env/reports.py:20–21,35`.

The dictionary redactor recognizes exactly `session`/`cookie` after normalization, but only matches suffixes password/token/secret/apikey. It therefore retains `d1env_session` and `Set-Cookie` fields. Its text regexp starts at a word boundary before `session`, so a log value `d1env_session=SAMPLE` is also retained. This leaves the Task 7 known-session/credential guarantee incomplete if a report contains an app cookie/header or corresponding diagnostic text.

Actual focused reproduction, using invented sample values only:

```python
probe = {
    'd1env_session': 'REVIEW_SAMPLE_SESSION',
    'Set-Cookie': 'd1env_session=REVIEW_SAMPLE_COOKIE; HttpOnly',
    'log': 'd1env_session=REVIEW_SAMPLE_TEXT',
}
redact(probe, True, set())
```

Actual output identified all three fields as retaining the sample value. Remediation: cover the app's cookie name, Set-Cookie/cookie header names, nested maps/lists, and credential assignments in diagnostic text. Credentials must remain redacted even with identifier masking disabled; failure evidence and provenance must remain readable.

Repair observed in `45fd3cb`: explicit normalized d1envsession/setcookie/xcsrftoken names and d1env_session assignment text were added. Re-running the original invented-value probe returned no fields retaining the sample value. Focused security/report tests passed 14/14 (exit 0), and the final backend suite below also passes.

### P2, repaired: Non-ASCII authentication material raised an unhandled exception

Observed location: `src/d1env/web/security.py:28,41`.

`hmac.compare_digest(str, str)` only supports ASCII strings. BootstrapRequest permits any string satisfying its length bounds. A same-origin POST containing `'中' * 16` therefore reaches the comparison and produces HTTP 500 rather than a structured authentication rejection. An authenticated POST with non-ASCII bytes in `X-CSRF-Token` follows the same failure path.

The initial actual focused API reproduction used FastAPI TestClient with `raise_server_exceptions=False`, a temporary state directory, and an invented ASCII bootstrap token; malformed Unicode bootstrap produced HTTP 500. The analogous CSRF failure was identified from the same string comparison code, not separately reproduced before repair. This is an error-handling failure, not an observed authentication bypass.

Remediation: reject malformed token character sets or compare encoded bytes, return structured 401/403, and retain one-use bootstrap semantics. Add tests that invalid Unicode material does not crash and legitimate bootstrap still works afterward.

Repair observed in `45fd3cb`: comparison arguments now use encoded bytes, with new bootstrap/CSRF regression tests. Actual post-repair focused API results: malformed Unicode bootstrap HTTP 401, subsequent valid bootstrap HTTP 200, malformed non-ASCII CSRF HTTP 403. No real credentials were printed.

### P2, repaired: Telemetry could claim PASS with null or nonfinite samples

Observed location before repair: `src/d1env/models.py:244–249`, `Telemetry.no_unverified_health`.

An actual model probe accepted `Telemetry(status='PASS', observed_at=utcnow(), origin='sdk')` and serialized both battery and pose to null. A fresh PASS sample with `battery_percent=float('nan')` similarly serialized battery to null. This contradicted A10 at the shared model boundary; the current doctor itself correctly reports missing robot telemetry as UNKNOWN.

Repair observed in `39bdb0f`: PASS requires non-null battery and nonempty pose, timestamp, origin, and a fresh observation. `allow_inf_nan=False` rejects supplied nonfinite values, including those in pose. Regression `tests/test_catalog.py::test_null_or_nonfinite_samples_cannot_be_normal_telemetry` covers the boundary. No SDK call or hardware claim was introduced.

### P2, repaired: Retrying a restored interrupted job changes the original plan

Observed location: `frontend/src/App.tsx:19–20,51–59,128–136` before repair.

The page restores only the persisted job/events. It reconstructs `verify_failure` from one specific failure code, but an INTERRUPTED job has `WORKER_INTERRUPTED`; the selected request consequently remains the default success scenario. Retry always previews this current request rather than using the restored job's saved plan. An interrupted failure-scenario job can therefore be retried as a success-scenario job without the user choosing a configuration change.

Actual reproduction used isolated headless system Chrome with all API responses intercepted as explicitly invented fixtures. Local storage contained a restored job whose plan was `review-verify_failure`, state INTERRUPTED, and error WORKER_INTERRUPTED. Clicking “重试 MOCK 演示” produced:

```json
{"restoredPlanId":"review-verify_failure","retryPreviewScenario":"success","submittedPlanId":"review-success"}
```

The probe did not create a real backend job or consume a real bootstrap. Remediation: preserve the saved original plan/request across refresh; for example, retry `job.plan_id` with a new idempotency key and let the backend revalidate its saved request. Add a regression for an INTERRUPTED fault-injection job restored after refresh, asserting the original plan is submitted with a fresh key.

Repair observed in final `App.tsx`: retry validates MOCK scope, submits the persisted `job.plan_id` directly, and creates a fresh key; the backend still revalidates its saved original request. The frontend agent recorded the interrupted restore regression failing before implementation, then passing. Reviewer independently ran the final 12-test frontend suite and repeated the same isolated Chrome fixture probe against the rebuilt UI:

```json
{"status":"PASS","restoredPlanId":"review-verify_failure","previewCalls":0,"submittedPlanId":"review-verify_failure","newKeyPresent":true}
```

This actual browser probe again intercepted all API responses and created no real backend job.

### P2, repaired: Optional IP masking retains IPv6 in diagnostic text

Observed location: `src/d1env/reports.py:38–40` before repair.

The recursive redactor masks values under known `ip` fields, but its free-text address regexp matches IPv4 only. The generic IP masking choice consequently retains IPv6 in diagnostic messages. Actual invented-value model probe:

```text
redact('MOCK evidence: device [2001:db8::1], ip=fe80::abcd%en0', True, set())
=> 'MOCK evidence: device [2001:db8::1], ip=fe80::abcd%en0'
```

No actual host IP was read. Remediation: validate candidate IPv6 text with the standard library and mask valid addresses, including bracketed/zone forms, while preserving failure evidence and optional unmasked export. Add a focused regression; no network operation is needed.

The first repair used `ipaddress.IPv6Address`; bracketed, scoped, and IPv4-mapped examples passed. A follow-up reviewer probe found the same issue remained for no-space diagnostic labels (`ip:2001:db8::1` and `peer:2001:db8::1`), because the candidate included the label delimiter. This was repaired too, preserving that delimiter. Independent final probes now mask bracketed/scoped/mapped addresses and `ip:`, `peer:`, and `loopback:::1` forms; disabling identifier masking preserves the original samples. Final reports/process tests passed 14/14 and static checks passed. All values were invented; no host IP was read.

## Passed focused checks

Actual command:

```text
.venv/bin/python -m pytest tests/test_security.py tests/test_api.py tests/test_jobs.py tests/test_recovery.py tests/test_reports.py tests/test_process.py tests/test_service.py -q
```

Actual exit code 0: **49 passed in 8.67s**. These existing tests did not cover either reproduced finding above.

Actual post-fix command `.venv/bin/python -m pytest tests/test_catalog.py tests/test_security.py tests/test_reports.py tests/test_process.py -q`: exit 0, **30 passed in 0.90s**. This includes the null/nonfinite telemetry and malformed UTF-8 bounded-output regressions.

Actual final backend command `.venv/bin/python -m pytest -q` at `39bdb0f`: exit 0, **88 passed in 9.35s**. Actual frontend command `npm run test -- --run` in `frontend/`: exit 0, **11 passed in 1.91s**, before the interrupted-plan repair.

Final independent reviewer closure at `0b08620`: `.venv/bin/python -m pytest -q`, exit **0**, **90 passed in 9.66s**; `npm run test -- --run`, exit **0**, **12 passed in 1.79s**. The final backend count includes the timeout-marker bound and IPv6 regressions. The final frontend count includes the saved-plan interrupted retry regression.

Actual reviewer static commands `.venv/bin/ruff check src tests` and `.venv/bin/mypy src`, repeated after the last reports repair: both exit 0; all Ruff checks passed and mypy reported no issues in 17 source files.

Read evidence reviewed: fixed known probe argv with `shell=False`, default Docker context and cleared Docker redirection environment variables; only registered `local` request target; server-saved plans and fresh revalidation; SQLite active-job uniqueness and POSIX target lease; actual two-process tests; crash/restart resource inventory and INTERRUPTED state; cancellation device/inode ownership; mock-only operation whitelist/readiness evidence; Host/Origin/SameSite/CSRF/bootstrap restrictions; JSON/SSE and React text escaping. No additional arbitrary execution, real robot path, duplicate worker, or unowned deletion was identified in this reviewed scope.

## Frontend checks and limits

Source reviewed: initialization removes bootstrap from the fragment before network/rendering; session+CSRF are held in memory; job IDs are URL-encoded; state polling is guarded by current job identity; duplicate clicks use synchronous action locks; terminal states stop polling; React renders hostile event text and evidence as text; real profiles/motion controls remain disabled; scope and unavailable telemetry stay explicit. Report identifier masking is now selectable and defaults true; credential masking remains mandatory. CANCELLED and INTERRUPTED do not use the success icon.

Actual isolated system-Chrome probe of a delayed old preview followed by a scenario change passed after the generation guard: preview requests were success then verify_failure, and the submitted plan was `review-verify_failure`. All API responses in this probe were mocked; it proves UI state behavior, not backend operation or Docker health. The default Playwright headless-shell launch failed because its bundled browser cache was absent; an installed system Chrome in a separate headless profile was used without installing a browser.

The frontend agent's actual final E2E record was read: `work/evidence/task6-e2e.log` reports one browser test passed in **7.1s**; `task6-summary.md` records the real loopback API command and exit **0** after the retry repair. Its scope is authenticated MOCK success, duplicate clicks, successful and failed job refresh, fault injection rendered as text, JSON/Markdown download, and original retry plan plus new key. This reviewer inspected the actual success/failure viewport screenshots with `view_image`: both prominently display MOCK, unverified real Docker/hardware, UNKNOWN/null telemetry, and disabled motion. Those images were captured by the frontend agent, not generated by this reviewer. The real E2E covers failed-job refresh/retry; INTERRUPTED retry is additionally covered by the unit regression and independent intercepted-API browser probe.

NOT_RUN by this reviewer: independent real full-stack browser E2E and screenshot capture (owned by the frontend agent); direct actual Docker daemon probing or container lifecycle; Linux fresh-VM installation/distribution; manufacturer SDK loading/calls; robot/network/hardware/firmware/motion/stop validation. No M3+ behavior was tested or inferred. Backend local probe and mock unit/process evidence cannot be counted as real Docker lifecycle or hardware PASS.

No additional arbitrary execution, remote-target escape, authentication bypass, duplicate worker, or unowned deletion was identified in the reviewed M0–M2 implementation. All five reproduced P2 findings are closed. Future stages require their own fresh review and actual integration evidence.

## Acceptance review mapping

PASS below is limited to the recorded M0 static audit and M1–M2 software/MOCK behavior. It does not upgrade Docker lifecycle or hardware verification.

| ID | Review result | Evidence and limits |
|---|---|---|
| A01 | PASS, static source audit | Six actual checkout commits, 83 actual file hashes, validated lock schema; license/binary limitations remain explicit. |
| A02 | PASS, software | Strict catalog/request validation and real-profile blockers; no firmware/artifact guess enables execution. |
| A03 | PASS, software | CPU MOCK/diagnostics skip GPU without blocking. |
| A04 | PASS, injected software cases | Missing/permission/daemon/timeout classified; fixed read-only argv; no permission escalation. This is not real container lifecycle evidence. |
| A05 | PASS, software | Strict data-only requests/config, unknown fields and unsafe inputs rejected; no arbitrary shell, remote target, or executable YAML path. |
| A06 | PASS, MOCK/process tests | Stable saved plan, SQLite idempotency/unique active target, actual separate-process lease tests, duplicate UI click guard. |
| A07 | PASS, MOCK/process tests | Dead nonterminal job becomes INTERRUPTED with inventory; live lease survives another service instance; no automatic success/rearm. |
| A08 | PASS, MOCK ownership tests | Cancellation waits for worker; cleanup requires registered device/inode identity and preserves unrelated maps/bags/resources. |
| A09 | PASS, TestClient plus peer browser evidence | Host/Origin/session/CSRF/bootstrap rejections; non-ASCII failures now structured; authenticated same-origin browser flow. |
| A10 | PASS, software | Missing/old/nonfinite telemetry cannot claim PASS; current robot state stays UNKNOWN/null in UI. |
| A11 | PASS, actual software UI evidence | Source, real frontend-agent screenshots, API/report MOCK scope, disabled real/motion choices; no Docker/hardware success claim. |
| A12 | PASS, software/MOCK integration | Saved job refresh, fault evidence, pure-text hostile logs, original-plan retry, JSON/Markdown download, mandatory credentials and optional IPv4/IPv6/serial masking. |

The audit redaction probes used invented sample strings; no real session/bootstrap values were copied to this review artifact. Temporary API state was confined to a temporary directory and removed by the probe.
