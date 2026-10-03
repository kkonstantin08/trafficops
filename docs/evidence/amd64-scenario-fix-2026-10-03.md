# AMD64 controller 503 fix и полный scenario — 3 октября 2026

Проверки выполнены агентом через SSH на той же Ubuntu 24.04.4 LTS AMD64 VM: amd64/x86_64, 4 CPU, MemTotal 4015132 KiB, swap 0B. Credentials, cookies, CSRF и адреса VM исключены. Этот этап применяет исправление к уже установленному стенду; исходный clean bootstrap/deploy доказан предыдущими evidence.

## Previous failure

Old tested SHA `6c611c46862061caba371b27b9df2e062f2753be`, implementation `e24aa05c9618d9bb462515371088b816b566eb1b`. Первый полный scenario: make exit 2, script exit 1, GET /api/overview HTTP 503 после успешного POST /api/release/start. Envoy: UC, upstream_reset_before_response_started{connection_termination}, duration=0; controller restart=0. [Предыдущий failed scenario](amd64-clean-scenario-2026-10-03.md), documentation commit `042dfed91d56cfae5263bca684bde1390596921a`. Prometheus unknown не установлен как причина 503.

## Investigation

Прочитаны scripts/verify-scenario.py, controller/api.py, runtime.py, clients.py, store.py, controller deployment/route и Gateway/Envoy manifests. Scenario делает GET polling каждые 5s через Gateway, без retry. Проверены фактические pinned зависимости и живые server/proxy настройки. У установленного Uvicorn 0.54.0 значение Config.timeout_keep_alive по inspect.signature равно 5; прямой TCP /healthz к controller Service закрылся EOF через 5.001s простоя. До исправления в Envoy controller cluster не было explicit typed_extension_protocol_options. У установленного BackendTrafficPolicy CRD default connectionIdleTimeout — 1 hour.

Значения и семантика также сверены с первичными источниками: [Uvicorn settings](https://www.uvicorn.org/settings/) и [Envoy Gateway v1.9 HTTPTimeout](https://gateway.envoyproxy.io/v1.9/api/extension_types/). Runtime measurements относятся именно к этой VM, документация не заменяет их.

## Reproduction before fix

Только безопасные GET /api/overview с query request_id; без mutations и без login/публикации auth. Диагностические scripts вне checkout (/tmp), stdlib urllib/http.client; они не меняют production/scenario client. Через Gateway сохранён обычный controller route. Прямой controller Service использован только для сравнения.

| Проверка | Интервалы | До fix |
| --- | --- | --- |
| Новый downstream connection, Gateway + Service | 4/5/6/10s, 3 цикла, warm + after | 48 GET, все 200 |
| Новый connection, Gateway boundary | 4.99/5.00/5.01s, 12 пар | 24 GET, все 200 |
| Постоянный downstream HTTP connection, Gateway | 4.999/5.000/5.001s, 12 пауз | 13 GET: 10×200, 3×503 |

Persistent run persistent-2f7c5df304: 503 на indices 2, 5, 7. Envoy matching records: 2026-10-03T19:26:10.207Z, 19:26:25.284Z, 19:26:35.320Z; во всех UC / upstream_reset_before_response_started{connection_termination} / duration=0. Всего 61 Gateway access record (58×200, 3×503); 24 прямых Service GET не проходят через Envoy. Controller restart count 0; relevant controller logs не дали exception/crash. Это воспроизведение того же failure signature, но не идентичного полного POST→GET scenario.

## Root cause

**Not conclusively proven; most likely cause:** race reuse pooled upstream connection с server-first idle close Uvicorn около 5s. Доказаны actual default 5s, server EOF 5.001s, три Gateway UC/connection_termination около этой границы без pod restart и отсутствие такого failure у прямых Service GET. Точный порядок TCP FIN/reuse не захватывался packet capture; поэтому гипотеза о причине исходного scenario не объявляется окончательно доказанной. Runtime fix устраняет наблюдаемый failure mode согласованием timeout ordering, а не проглатыванием 5xx.

## Fix

Functional commit `0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f`:

- deploy/controller.yaml: explicit Uvicorn --timeout-keep-alive 30.
- deploy/controller-route.yaml: BackendTrafficPolicy trafficops-panel-idle-timeout, только HTTPRoute trafficops-panel в namespace trafficops, connectionIdleTimeout 15s.
- scripts/validate_manifests.sh: pinned BackendTrafficPolicy CRD schema с SHA256, включён в schema validation.
- tests/test_clients.py: ожидаемые args, scope policy и 15 < 30.

Envoy закрывает idle upstream раньше server (15s < 30s), с запасом 15s; обычные 5s polls и 10s интервалы укладываются в proxy timeout. Это finite idle limits для connection lifecycle, не изменение request deadlines: прежние request/backendRequest 100s сохранены. Увеличение только server timeout без proxy ordering оставило бы новый boundary race. Retry не добавлен ни для GET, ни для POST. UI, canary policy, Prometheus и Fluentd не изменены.

## Regression tests

Новый test_controller_and_gateway_idle_timeouts_avoid_server_first_close сначала дал ожидаемый RED на отсутствующем explicit timeout, затем GREEN. Это config regression contract, не имитация сетевого race; runtime reproduction/retest приведены отдельно.

Полный локальный suite с pinned requirements.lock: python3 -m unittest discover -s tests -p 'test_*.py' — 41/41 PASS. bash -n для platform/bootstrap/deploy/verify/validate_manifests PASS; node --check web/app.js и node tests/test_release_ui.js PASS; scripts/validate_manifests.sh — 37 resources valid, 0 invalid/errors/skipped; git diff --check PASS. Local Python 3.14; CI использует pinned Python 3.12.12. Deprecated Starlette/httpx warning не является test failure.

## CI

Functional exact SHA: [CI 37148162533](https://github.com/kkonstantin08/trafficops/actions/runs/37148162533) **success**, включая unit tests, shell/JS, schema и AMD64/ARM64 image build. Только после green CI обновлена VM.

## VM update

Pre-update 2026-10-03T19:33:59Z: SHA 6c611c46862061caba371b27b9df2e062f2753be, checkout clean; node Ready, 17 running workloads healthy, restarts 0, штатный Completed retention CronJob; route 100/0, APP_FORCE_ERRORS=false. Выполнены git fetch origin fix/amd64-bootstrap и git checkout 0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f. Exact detached HEAD подтверждён git rev-parse HEAD, git status --short пустой. Перед deploy SSH transport reconnect потребовался после закрытия прежней сессии; runtime не менялся этим reconnect.

## Deploy after fix

Только make deploy, без ручного kubectl patch. 2026-10-03T19:34:14Z → 19:34:42Z; DEPLOY_EXIT=0. Built-in verify: Gateway 200/v1, marker verify-b760a7b9633b4b179c4bcb29ad672619 найден Fluentd, 5 Prometheus jobs со свежими samples, panel/controller 200. Controller штатно заменён Recreate deployment: old trafficops-controller-54ffbd7dd4-r82d7 → trafficops-controller-6d99494c76-pjqxg, new pod Running/Ready, restart 0. Остальные приложения не заменялись; route 100/0 сохранён.

## Targeted verification after fix

Повторены те же три scripts/interval sets: persistent 13/13 HTTP 200, wide 48/48 HTTP 200, boundary 24/24 HTTP 200. Всего 85 GET, 0 failures. Envoy все 61 matching Gateway records: 200, flags '-', 0 UC. Прямые 24 Service GET дополнительно 200. Runs: persistent-ffc64720cc, get-repro-6cdd4d9b1c, get-repro-03e22993d7. Controller logs только startup, restart 0.

Policy Accepted=True, observedGeneration=1; live controller args timeout 30. Envoy admin config_dump через временный loopback-only port-forward подтвердил controller cluster httproute/trafficops/trafficops-panel/rule/0: common_http_protocol_options.idle_timeout=15s. Port-forward остановлен после read-only capture. Данные после fix подтверждают устранение failure в этом ограниченном тесте; это не длительный soak.

## Full scenario after fix

Выполнен **один** повторный make verify-scenario, после green targeted retest. Start 2026-10-03T19:39:10Z; end 19:43:46Z; **SCENARIO_EXIT=0**. PYTHONUNBUFFERED=1 использован только для своевременного вывода стадий. set -o pipefail, tee ~/trafficops-scenario-after-fix.log, exit взят из PIPESTATUS[0]. Ручных mutations во время scenario не было; script не изменён и не повторялся до случайного PASS.

| Стадия | Фактическое доказательство |
| --- | --- |
| Healthy canary | release-start 90/10, started_at=1791056482.0692146; traffic 1376 sent / 0 failed |
| Полное свежее окно 60s | check 1791056545.1147668: прошло 63.0456s; sample_time=1791056535.846, age=9.2688s, target_up=true, requests=121, errors=0, ratio=0, observe/breaches=0 |
| Complete v2 | operation succeeded 1791056548.7154725, weights 0/100; дополнительная complete decision requests=118/errors=0, свежий sample=1791056545.846; script Gateway HTTP 200/version v2 |
| Manual rollback | succeeded 1791056549.7721498, weights 100/0, confirmed_version=v1; script Gateway HTTP 200/version v1 |
| Fault injection | incident-errors enabled=true 1791056549.7873433; failed canary started_at=1791056550.8540564, weights 90/10; traffic 1534 sent/95 failed |
| Breach 1 | check 1791056615.1859434: 124 requests, 70 errors, ratio 0.5658959663045373 (>5%), target_up=true, sample 1791056605.846; breaches 1 |
| Breach 2 | check 1791056625.1957626: 120 requests, 90 errors, ratio 0.7503667776685174 (>5%), target_up=true, sample 1791056615.846; breaches 2/state rollback, rollback_confirmed=true |
| Automatic rollback | succeeded 1791056626.245683, reason automatic rollback: 5xx threshold exceeded, confirmed_version=v1; script independently confirms Gateway v1 |
| Cleanup | stop traffic; enabled=false; manual cleanup rollback 100/0; logout HTTP 200; no CLEANUP ERROR |

Breach checks разделены 10.0098s; обе после полного окна fault canary (64.3319s и 74.3417s) и с sample age около 9.34s. Requests/errors в decision округлены кодом; error_ratio использует исходные PromQL increase, поэтому не обязан в точности равняться отношению этих округлённых чисел. Это реальные свежие v2 5xx, не controller HTTP 503. Во всех 47 scenario controller-route Envoy records HTTP 200, flags '-', no UC; включая login/start/complete/rollback/stop/errors/logout. Ранние unknown до полного окна штатно не разрешали progression.

Последний reason=manual rollback в final state относится к cleanup и **не заменяет** отдельную journal запись automatic rollback выше. Sessions/Secret/CSRF не выбирались при read-only SQLite capture; только operations с начала этого запуска и state release/traffic/incident.

## Final state

Capture 2026-10-03T19:45:14Z: exact tested SHA 0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f, checkout clean. Node Ready; 17 long-running pods Running/Ready, restart 0, штатный retention CronJob Completed. New controller pod trafficops-controller-6d99494c76-pjqxg healthy. Route 100/0; APP_FORCE_ERRORS=false в ConfigMap и фактическом mounted file /etc/trafficops/APP_FORCE_ERRORS внутри demo-v2. Release rolled-back, reason manual rollback (cleanup), reconcile_required=false; traffic stopped.

Gateway /demo HTTP 200/version v1, request_id 64c24b22-77ed-4c97-af31-10e6a5998d39; controller /healthz 200/status ok; /api/overview 200 с согласованным final release/traffic. RAM 3.8Gi total/2.1Gi available, swap 0B; disk 58G/52G available. Failed systemd units 0. Read-only kernel journal 20 minutes: нет out of memory/oom-kill/killed process записей. На VM rg отсутствует: фильтр повторён установленным grep, ничего не устанавливалось. Controller log содержит только startup, без runtime exception.

## Manual fixes

None.

Только штатный make deploy применил committed fix. Все release/traffic/errors mutations выполнены самим scenario; дополнительных runtime patches/ручных recovery операций не было.

## Result

**PASS**: targeted воспроизведение до fix 3/13 HTTP 503 UC → после 0/85; единственный full scenario after fix exit 0, все требуемые стадии подтверждены. Точный TCP race исходного failed scenario остаётся most likely cause, а не conclusively proven. Долгий soak, повторный bootstrap/idempotency, security negative tests и ручная visual UI проверка этим этапом не выполнялись. Повторный deploy здесь служит применением конкретного fix и не объявляется отдельной полной проверкой идемпотентности.

main остаётся 20e5d247b4b044cec80f1a3c3f03abd940c3574c; merge не выполнялся. Acceptance/README/passport не менялись. Evidence добавляется отдельным documentation-only commit в fix/amd64-bootstrap; функциональная VM остаётся на exact fix SHA.

## Captured records

### Persistent reproduction before / after

```json
{"run": "persistent-2f7c5df304", "index": 0, "time": 1791055560.1301184, "status": 200}
{"run": "persistent-2f7c5df304", "index": 1, "time": 1791055565.1728325, "status": 200}
{"run": "persistent-2f7c5df304", "index": 2, "time": 1791055570.2070212, "status": 503}
{"run": "persistent-2f7c5df304", "index": 3, "time": 1791055575.2094483, "status": 200}
{"run": "persistent-2f7c5df304", "index": 4, "time": 1791055580.2475898, "status": 200}
{"run": "persistent-2f7c5df304", "index": 5, "time": 1791055585.28369, "status": 503}
{"run": "persistent-2f7c5df304", "index": 6, "time": 1791055590.2858818, "status": 200}
{"run": "persistent-2f7c5df304", "index": 7, "time": 1791055595.3205264, "status": 503}
{"run": "persistent-2f7c5df304", "index": 8, "time": 1791055600.3216994, "status": 200}
{"run": "persistent-2f7c5df304", "index": 9, "time": 1791055605.3600066, "status": 200}
{"run": "persistent-2f7c5df304", "index": 10, "time": 1791055610.3956945, "status": 200}
{"run": "persistent-2f7c5df304", "index": 11, "time": 1791055615.4324002, "status": 200}
{"run": "persistent-2f7c5df304", "index": 12, "time": 1791055620.4712427, "status": 200}
```

```json
{"run": "persistent-ffc64720cc", "index": 0, "time": 1791056116.6431987, "status": 200}
{"run": "persistent-ffc64720cc", "index": 1, "time": 1791056123.6350417, "status": 200}
{"run": "persistent-ffc64720cc", "index": 2, "time": 1791056128.671277, "status": 200}
{"run": "persistent-ffc64720cc", "index": 3, "time": 1791056133.713772, "status": 200}
{"run": "persistent-ffc64720cc", "index": 4, "time": 1791056138.7498817, "status": 200}
{"run": "persistent-ffc64720cc", "index": 5, "time": 1791056143.7894144, "status": 200}
{"run": "persistent-ffc64720cc", "index": 6, "time": 1791056148.8248546, "status": 200}
{"run": "persistent-ffc64720cc", "index": 7, "time": 1791056153.87008, "status": 200}
{"run": "persistent-ffc64720cc", "index": 8, "time": 1791056158.905144, "status": 200}
{"run": "persistent-ffc64720cc", "index": 9, "time": 1791056163.9443269, "status": 200}
{"run": "persistent-ffc64720cc", "index": 10, "time": 1791056168.982769, "status": 200}
{"run": "persistent-ffc64720cc", "index": 11, "time": 1791056174.0207078, "status": 200}
{"run": "persistent-ffc64720cc", "index": 12, "time": 1791056179.0611022, "status": 200}
```

### Full scenario transcript

```text
./scripts/verify-scenario.py
Resetting demo-v2 error switch; waiting 130 seconds for ConfigMap projection.
Running healthy canary with 20 requests/s for at most 180 seconds.
Healthy canary has a complete fresh window with at least 30 v2 requests.
Healthy release completed and HTTP v2 was confirmed through Gateway.
Manual rollback confirmed HTTP v1 through Gateway.
Enabling controlled v2 errors and running a failed canary.
Failed canary automatically rolled back; its fresh 5xx decision and HTTP v1 were confirmed.
Scenario passed; finally stopped traffic, disabled v2 errors, manually rolled back, and logged out.
SCENARIO_EXIT=0
```

### Full operation journal and safe state

```text
{"id": "b35479250b874316875c31ee00b0bd24", "kind": "incident-errors", "status": "succeeded", "created": 1791056350.9912956, "updated": 1791056351.0040162, "reason": null, "details": {"enabled": false, "intent": "persisted", "note": "v2 receives the ConfigMap through the fixed pod mount"}}
{"id": "1f7fe0d944df4c81bbd8948fb4f95252", "kind": "traffic-start", "status": "succeeded", "created": 1791056481.0151362, "updated": 1791056549.7822635, "reason": null, "details": {"status": "stopped", "run_id": "run-e6837ab43c7f4e20", "rate": 20, "duration": 180, "path": "/demo", "sent": 1376, "failed": 0, "started_at": 1791056481.0124393, "finished_at": 1791056549.780344}}
{"id": "2132593c31b44a4d89e56943f84ff263", "kind": "release-start", "status": "succeeded", "created": 1791056481.0231805, "updated": 1791056482.0720494, "reason": null, "details": {"weights": {"v1": 90, "v2": 10}, "intent": "persisted", "started_at": 1791056482.0692146}}
{"id": "8b85dd55455b423eb66d8a271d8fa8cc", "kind": "canary-check", "status": "succeeded", "created": 1791056485.0545995, "updated": 1791056485.0545995, "reason": "canary window is not complete", "details": {"metrics": {"requests": 0.0, "errors": 0.0, "sample_time": 1791056475.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056485.0545971}}
{"id": "9655feb956ae4a06a1aa757bd52829a2", "kind": "canary-check", "status": "succeeded", "created": 1791056495.0643568, "updated": 1791056495.0643568, "reason": "canary window is not complete", "details": {"metrics": {"requests": 9.6, "errors": 0.0, "sample_time": 1791056485.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056495.064355}}
{"id": "8f1581d988b74cd4bba23a43d0fbfae1", "kind": "canary-check", "status": "succeeded", "created": 1791056505.0749917, "updated": 1791056505.0749917, "reason": "canary window is not complete", "details": {"metrics": {"requests": 34.8, "errors": 0.0, "sample_time": 1791056495.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056505.0749898}}
{"id": "0eedf74950a64839bad188cebb0f0bf5", "kind": "canary-check", "status": "succeeded", "created": 1791056515.0843363, "updated": 1791056515.0843363, "reason": "canary window is not complete", "details": {"metrics": {"requests": 58.8, "errors": 0.0, "sample_time": 1791056505.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056515.0843349}}
{"id": "678adaaf6aa743ed958b22e76777631b", "kind": "canary-check", "status": "succeeded", "created": 1791056525.094247, "updated": 1791056525.094247, "reason": "canary window is not complete", "details": {"metrics": {"requests": 82.8, "errors": 0.0, "sample_time": 1791056515.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056525.094246}}
{"id": "0631e0c3917644cb93ddbc23986a6329", "kind": "canary-check", "status": "succeeded", "created": 1791056535.103227, "updated": 1791056535.103227, "reason": "canary window is not complete", "details": {"metrics": {"requests": 106.8, "errors": 0.0, "sample_time": 1791056525.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056535.1032257}}
{"id": "9f706d4a1b5c43b58caf4ace0546bb3f", "kind": "canary-check", "status": "succeeded", "created": 1791056545.1147714, "updated": 1791056545.1147714, "reason": "within error threshold", "details": {"metrics": {"requests": 121, "errors": 0, "sample_time": 1791056535.846, "target_up": true, "state": "observe", "breaches": 0, "reason": "within error threshold", "error_ratio": 0.0}, "checked_at": 1791056545.1147668}}
{"id": "279df80710644a218f90df6d023503df", "kind": "release-complete", "status": "succeeded", "created": 1791056547.6130004, "updated": 1791056548.7154725, "reason": null, "details": {"intent": "persisted", "weights": {"v1": 0, "v2": 100}, "metrics": {"requests": 118, "errors": 0, "sample_time": 1791056545.846, "target_up": true, "state": "observe", "breaches": 0, "reason": "within error threshold", "error_ratio": 0.0}}}
{"id": "89d84c8de7094ac4bdc37d7072da7843", "kind": "release-rollback", "status": "succeeded", "created": 1791056548.7226253, "updated": 1791056549.7721498, "reason": "manual rollback", "details": {"route": {"v1": 100, "v2": 0}, "intent": "persisted", "weights": {"v1": 100, "v2": 0}, "confirmed_version": "v1", "reason": "manual rollback"}}
{"id": "154cef99240b451b9f8eabf88aac9dc8", "kind": "incident-errors", "status": "succeeded", "created": 1791056549.7873433, "updated": 1791056549.800076, "reason": null, "details": {"enabled": true, "intent": "persisted", "note": "v2 receives the ConfigMap through the fixed pod mount"}}
{"id": "301b5a1aa3f6436a9bd0a52aeaf786e7", "kind": "traffic-start", "status": "succeeded", "created": 1791056549.8066916, "updated": 1791056626.5057275, "reason": null, "details": {"status": "stopped", "run_id": "run-681dea337e754848", "rate": 20, "duration": 180, "path": "/demo", "sent": 1534, "failed": 95, "started_at": 1791056549.8046007, "finished_at": 1791056626.5030522}}
{"id": "40c18641838e4d35bdc3841f4330dc07", "kind": "release-start", "status": "succeeded", "created": 1791056549.8123326, "updated": 1791056550.8562763, "reason": null, "details": {"weights": {"v1": 90, "v2": 10}, "intent": "persisted", "started_at": 1791056550.8540564}}
{"id": "8a2787f42eb745c9b5a11588aa0a79cf", "kind": "canary-check", "status": "succeeded", "created": 1791056555.1245022, "updated": 1791056555.1245022, "reason": "canary window is not complete", "details": {"metrics": {"requests": 118.8, "errors": 0.0, "sample_time": 1791056545.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056555.1245}}
{"id": "027f502a8b39476d8bf7c04342a1a505", "kind": "canary-check", "status": "succeeded", "created": 1791056565.1333568, "updated": 1791056565.1333568, "reason": "canary window is not complete", "details": {"metrics": {"requests": 142.79999999999998, "errors": 0.0, "sample_time": 1791056555.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056565.133355}}
{"id": "99803d0ace3b4391b25ac2e10e78b272", "kind": "canary-check", "status": "succeeded", "created": 1791056575.142829, "updated": 1791056575.142829, "reason": "canary window is not complete", "details": {"metrics": {"requests": 142.79999999999998, "errors": 0.0, "sample_time": 1791056565.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056575.1428275}}
{"id": "eba7658948164f34be4e2bf7ba015b2c", "kind": "canary-check", "status": "succeeded", "created": 1791056585.1520402, "updated": 1791056585.1520402, "reason": "canary window is not complete", "details": {"metrics": {"requests": 142.79999999999998, "errors": 0.0, "sample_time": 1791056575.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056585.1520386}}
{"id": "4a371ee5a6a842bc905ff76635b410b5", "kind": "canary-check", "status": "succeeded", "created": 1791056595.1635246, "updated": 1791056595.1635246, "reason": "canary window is not complete", "details": {"metrics": {"requests": 124.8, "errors": 0.0, "sample_time": 1791056585.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056595.1635234}}
{"id": "3e2c5738719748ebaac7351430534a7b", "kind": "canary-check", "status": "succeeded", "created": 1791056605.1734695, "updated": 1791056605.1734695, "reason": "canary window is not complete", "details": {"metrics": {"requests": 153.0825, "errors": 51.078300000000006, "sample_time": 1791056595.846, "target_up": 1.0, "state": "unknown", "breaches": 0, "reason": "canary window is not complete"}, "checked_at": 1791056605.173468}}
{"id": "8a05f9766e2d4363bb9d2a374984e6a0", "kind": "canary-check", "status": "succeeded", "created": 1791056615.185945, "updated": 1791056615.185945, "reason": "5xx threshold exceeded", "details": {"metrics": {"requests": 124, "errors": 70, "sample_time": 1791056605.846, "target_up": true, "state": "observe", "breaches": 1, "reason": "5xx threshold exceeded", "error_ratio": 0.5658959663045373}, "checked_at": 1791056615.1859434}}
{"id": "a54788c0c2b148d5ad1a1d790bea4af8", "kind": "canary-check", "status": "succeeded", "created": 1791056625.1957703, "updated": 1791056626.2474265, "reason": "5xx threshold exceeded", "details": {"metrics": {"requests": 120, "errors": 90, "sample_time": 1791056615.846, "target_up": true, "state": "rollback", "breaches": 2, "reason": "5xx threshold exceeded", "error_ratio": 0.7503667776685174}, "checked_at": 1791056625.1957626, "rollback_confirmed": true}}
{"id": "20e9da327365446098fafca73159c590", "kind": "release-rollback", "status": "succeeded", "created": 1791056625.1980503, "updated": 1791056626.245683, "reason": "automatic rollback: 5xx threshold exceeded", "details": {"metrics": {"requests": 120, "errors": 90, "sample_time": 1791056615.846, "target_up": true, "state": "rollback", "breaches": 2, "reason": "5xx threshold exceeded", "error_ratio": 0.7503667776685174}, "confirmed_version": "v1"}}
{"id": "67196fbc7bff4ce0a9f4c8e1cfbf71b6", "kind": "incident-errors", "status": "succeeded", "created": 1791056626.510652, "updated": 1791056626.534361, "reason": null, "details": {"enabled": false, "intent": "persisted", "note": "v2 receives the ConfigMap through the fixed pod mount"}}
{"id": "98209405fc58464bb9e9a0799e4b2f7d", "kind": "release-rollback", "status": "succeeded", "created": 1791056626.5382907, "updated": 1791056626.571191, "reason": "manual rollback", "details": {"route": {"v1": 100, "v2": 0}, "intent": "persisted", "weights": {"v1": 100, "v2": 0}, "confirmed_version": "v1", "reason": "manual rollback"}}
SAFE_STATE
{"key": "release", "value": {"status": "rolled-back", "weights": {"v1": 100, "v2": 0}, "reason": "manual rollback", "rolled_back_at": 1791056626.5692399, "reconcile_required": false}}
{"key": "traffic", "value": {"status": "stopped", "run_id": "run-681dea337e754848", "rate": 20, "duration": 180, "path": "/demo", "sent": 1534, "failed": 95, "started_at": 1791056549.8046007, "finished_at": 1791056626.5030522}}
```

### Deploy verification tail

```text
daemon set "node-exporter" successfully rolled out
daemon set "fluentd" successfully rolled out
persistentvolume/trafficops-controller-data configured
persistentvolumeclaim/trafficops-controller-data unchanged
serviceaccount/trafficops-controller unchanged
role.rbac.authorization.k8s.io/trafficops-controller unchanged
rolebinding.rbac.authorization.k8s.io/trafficops-controller unchanged
deployment.apps/trafficops-controller configured
service/trafficops-controller unchanged
httproute.gateway.networking.k8s.io/trafficops-panel configured
backendtrafficpolicy.gateway.envoyproxy.io/trafficops-panel-idle-timeout created
Waiting for deployment "trafficops-controller" rollout to finish: 0 of 1 updated replicas are available...
deployment "trafficops-controller" successfully rolled out
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   60m   v1.36.5   [REDACTED_IP]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       51m
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [REDACTED_IP]   True         51m

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     51m
httproute.gateway.networking.k8s.io/trafficops-panel               50m
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-b760a7b9633b4b179c4bcb29ad672619
Fluentd log verified within 30 seconds: request_id verify-b760a7b9633b4b179c4bcb29ad672619, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200
DEPLOY_EXIT=0
```

### Controller route requests during scenario

```json
{"start_time": "2026-10-03T19:39:10.396Z", "method": "GET", "x-envoy-origin-path": "/healthz", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 1}
{"start_time": "2026-10-03T19:39:10.399Z", "method": "POST", "x-envoy-origin-path": "/api/login", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 504}
{"start_time": "2026-10-03T19:39:10.904Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 83}
{"start_time": "2026-10-03T19:39:10.989Z", "method": "POST", "x-envoy-origin-path": "/api/incident/errors", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 16}
{"start_time": "2026-10-03T19:41:21.008Z", "method": "POST", "x-envoy-origin-path": "/api/traffic/start", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 10}
{"start_time": "2026-10-03T19:41:21.021Z", "method": "POST", "x-envoy-origin-path": "/api/release/start", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 1052}
{"start_time": "2026-10-03T19:41:22.074Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 34}
{"start_time": "2026-10-03T19:41:27.110Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:41:32.148Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 34}
{"start_time": "2026-10-03T19:41:37.184Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:41:42.222Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 39}
{"start_time": "2026-10-03T19:41:47.263Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:41:52.300Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 35}
{"start_time": "2026-10-03T19:41:57.337Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:42:02.374Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 35}
{"start_time": "2026-10-03T19:42:07.412Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 42}
{"start_time": "2026-10-03T19:42:12.456Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 40}
{"start_time": "2026-10-03T19:42:17.498Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 37}
{"start_time": "2026-10-03T19:42:22.537Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 35}
{"start_time": "2026-10-03T19:42:27.573Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:42:27.611Z", "method": "POST", "x-envoy-origin-path": "/api/release/complete", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 1106}
{"start_time": "2026-10-03T19:42:28.721Z", "method": "POST", "x-envoy-origin-path": "/api/release/rollback", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 1052}
{"start_time": "2026-10-03T19:42:29.777Z", "method": "POST", "x-envoy-origin-path": "/api/traffic/stop", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 8}
{"start_time": "2026-10-03T19:42:29.786Z", "method": "POST", "x-envoy-origin-path": "/api/incident/errors", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 16}
{"start_time": "2026-10-03T19:42:29.803Z", "method": "POST", "x-envoy-origin-path": "/api/traffic/start", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 6}
{"start_time": "2026-10-03T19:42:29.811Z", "method": "POST", "x-envoy-origin-path": "/api/release/start", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 1047}
{"start_time": "2026-10-03T19:42:30.859Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:42:35.897Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 35}
{"start_time": "2026-10-03T19:42:40.933Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 37}
{"start_time": "2026-10-03T19:42:45.972Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 40}
{"start_time": "2026-10-03T19:42:51.014Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 37}
{"start_time": "2026-10-03T19:42:56.053Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:43:01.091Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:43:06.129Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 38}
{"start_time": "2026-10-03T19:43:11.169Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 34}
{"start_time": "2026-10-03T19:43:16.205Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 42}
{"start_time": "2026-10-03T19:43:21.249Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 36}
{"start_time": "2026-10-03T19:43:26.287Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 37}
{"start_time": "2026-10-03T19:43:31.327Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 37}
{"start_time": "2026-10-03T19:43:36.367Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 40}
{"start_time": "2026-10-03T19:43:41.408Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 38}
{"start_time": "2026-10-03T19:43:46.448Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 42}
{"start_time": "2026-10-03T19:43:46.495Z", "method": "GET", "x-envoy-origin-path": "/api/operations", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 3}
{"start_time": "2026-10-03T19:43:46.499Z", "method": "POST", "x-envoy-origin-path": "/api/traffic/stop", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 8}
{"start_time": "2026-10-03T19:43:46.509Z", "method": "POST", "x-envoy-origin-path": "/api/incident/errors", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 27}
{"start_time": "2026-10-03T19:43:46.537Z", "method": "POST", "x-envoy-origin-path": "/api/release/rollback", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 35}
{"start_time": "2026-10-03T19:43:46.574Z", "method": "POST", "x-envoy-origin-path": "/api/logout", "response_code": 200, "response_flags": "-", "response_code_details": "via_upstream", "duration": 5}
```
