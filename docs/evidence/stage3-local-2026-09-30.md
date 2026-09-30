# Stage 3 local evidence — 2026-09-30

Environment: macOS Darwin arm64, Python 3.14.5. No Kubernetes/Ubuntu VM was contacted or modified.

## Local verification

- `python3 -m unittest discover -s tests -p 'test_*.py' -v` — 28 tests passed in 8.014s. This includes canary threshold/freshness decisions, controller authentication/Origin/CSRF and input bounds, route generation confirmation, raw Prometheus sample timestamps and non-finite metric handling, bounded traffic scheduling/progress, operation failure/reconciliation, demo behavior, log marker parsing, and bootstrap config checks.
- `bash -n scripts/deploy.sh scripts/verify.sh` — passed.
- `node --check web/app.js` — passed.
- `python3 -m compileall -q controller demo tests scripts` — passed.
- Ruby Psych parsed `deploy/*.yaml`; a structural assertion confirmed `containers` and pod `securityContext` are siblings in the controller PodSpec — passed.
- `git diff --check` — passed.

The test client emits a Starlette warning that using `httpx` with `starlette.testclient` is deprecated; the tests still pass.

## Not verified here

No image build, Kubernetes API/RBAC behavior, Gateway request, Prometheus target/sample, Fluentd delivery/search, panel login against the deployed controller, release canary/auto-rollback, pod replacement, clean/repeated deploy, or Ubuntu 24.04 run was performed. These remain live acceptance items; local fakes and unit tests are not evidence that the cluster path works. The bounded end-to-end `verify-scenario` command is stage 4 work.
