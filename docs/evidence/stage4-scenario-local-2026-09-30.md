# Stage 4 scenario tool local evidence — 2026-09-30

Environment: macOS Darwin arm64, Python 3.14.5. No Kubernetes/Ubuntu VM was contacted or modified.

- `python3 -m py_compile scripts/verify-scenario.py` — passed.
- `python3 scripts/verify-scenario.py --help` — passed without reading credentials or accessing the cluster.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v` — 29 tests passed in 8.026s. The scenario cleanup test simulates a traffic-stop failure, verifies that the error is returned, and confirms disabling v2 errors, manual rollback, and logout are still attempted.
- `make -n verify-scenario` — resolves to `./scripts/verify-scenario.py`.
- `node --check web/app.js` and `git diff --check` — passed.

The live healthy/failed canary, Gateway response checks, Prometheus samples, and cleanup against the VM have not been run. Use `make verify-scenario` only after deployment, when the route is stable at v1=100/v2=0 and no other demo traffic is running. The script refuses non-default canary settings and keeps credentials, cookies, and CSRF values out of output.
