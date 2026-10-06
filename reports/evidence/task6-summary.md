# Task 6 actual execution record

Date: 2026-10-06. Environment: macOS aarch64, Node 24.19.0, npm 11.17.0. Scope: frontend and actual local API integration; no robot, SDK, or real Docker lifecycle was run.

## Final checks

| Command (frontend directory) | Exit | Actual result | Evidence |
|---|---:|---|---|
| `npm ci` | 0 | Installed the actual generated lock; 113 packages audited, zero vulnerabilities after version correction | Tool output during initial setup |
| `npm run test -- --run` | 0 | 12 passed, 0 failed | `work/evidence/task6-unit-green.log` |
| `npm run build` | 0 | TypeScript check and Vite 8.3.3 production build completed | `work/evidence/task6-build.log` |
| `npm audit` | 0 | Zero reported vulnerabilities | `work/evidence/task6-audit.log` |
| `npx playwright install chromium` | 0 | Installed separate test Chromium 153.0.8010.12 (Playwright revision 1243), including headless shell | Tool output |
| `D1ENV_E2E_TOKEN_FILE=<private file> D1ENV_E2E_URL=http://[IP]:8765 npx playwright test` | 0 | One final real API browser test passed after review closure, 6.3 seconds; total 7.1 seconds | `work/evidence/task6-e2e.log` |

The private bootstrap file was read without printing its contents. Browser tracing/video/automatic failure screenshots were disabled; all screenshots were taken after the URL fragment was cleared. The test used its own headless browser, separate from the user's browser.

## Observed red and repair evidence

- Initial wizard tests: exit 1, 7 failed against the empty App scaffold; missing wizard navigation, statuses, job flow, blocking, and evidence. `task6-unit-red.log`.
- First implementation run: 5 passed / 2 failed because two UI text queries were ambiguous; narrowed queries to the intended visible evidence element.
- First build: exit 1 from fixture typing (`error_code` inferred as null only). Fixed fixture types to match the API models. Final build exit 0.
- Cancellation test with the action missing: exit 1, expected CANCELLED but observed PREFLIGHT. Implemented the current-job cancellation call and state update. `task6-cancel-red.log`.
- Delayed old-plan test: exit 1, old response suppressed the new scenario request. Added request generations so an outdated preview cannot replace the current scenario. `task6-stale-plan-red.log`.
- Optional identifier export and neutral cancellation icon tests: exit 1, 2 failed / 9 passed. Implemented checked-by-default masking choice, actual request option, report preview option, and neutral non-success terminal icon. `task6-export-options-red.log`.
- E2E attempt 1: exit 1 after the real job succeeded; completion text matched both heading and event. Changed to an exact heading locator. `task6-e2e-attempt1.log`.
- E2E attempt 2: exit 1 after success, refresh, and real fault injection; the fault message occurred in two persisted events. Selected the first visible literal fault message, while retaining the independent no-script-execution assertion. `task6-e2e-attempt2.log`.
- Review found restored INTERRUPTED jobs rebuilt the default success plan. Added a regression first: exit 1, expected the saved fault-injection plan but received the default plan. Explicit retry now sends the original `job.plan_id` with a fresh key; the backend revalidates its saved immutable request. Unit suite 12/12 and final real browser E2E both pass. `task6-interrupted-retry-red.log`. The E2E now reloads the failed job too and verifies retry preserves its plan ID. A passing pre-review E2E checkpoint is separately preserved as `task6-e2e-before-review.log`.
- An initial dependency candidate audit reported four development-tool advisories. Replaced them with available, fixed Vite 8.3.3, Vitest 5.0.3, plugin-react 6.1.2, and Playwright 1.63.0. A stale newly generated lock caused ERESOLVE exit 1 during that upgrade; regenerated that new lock rather than bypassing peer resolution. Final audit is zero.

## Actual screenshot sources

- `frontend/test-results/task6-mock-success.png`: full page from the completed real-backend MOCK browser flow.
- `frontend/test-results/task6-mock-success-viewport.png`: viewport from the same flow.
- `frontend/test-results/task6-mock-failure.png`: full page from labelled `verify_failure` fault injection.
- `frontend/test-results/task6-mock-failure-viewport.png`: viewport from the same failed flow.

Screenshots were inspected with `view_image`. They retain MOCK, unknown/null telemetry, disabled motion, and explicit unverified hardware/Docker scope. No generated image was used as test evidence.

## Verified scope

Chinese five-step navigation; disabled, explained real mode and hardware choices; authenticated same-origin requests with write CSRF header; immediate bootstrap fragment removal; no client HostFacts injection; null/UNKNOWN telemetry; same current key on repeated submit; saved job ID restoration on refresh; clear fault code/step/next action; HTML-like log text rendered without execution; report mask choice; actual JSON and Markdown download contents; original saved plan plus fresh key on explicit retry. Cancel, unavailable-session behavior, and interrupted restore retry are unit-tested; the end-to-end browser test covers success/failure, both successful and failed job refresh, duplicate clicks, export, and retry.

## Not verified

Real Docker lifecycle, vendor SDK, robot telemetry, firmware compatibility, motion, hardware stop/disconnection behavior, final user installation package, or production distribution. Task 6 did not commit or push changes.
