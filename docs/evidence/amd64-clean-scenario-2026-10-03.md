# AMD64 clean full scenario — 3 октября 2026

## Environment

Та же VM Ubuntu 24.04.4 LTS, amd64/x86_64, 4 CPU, MemTotal 4015132 KiB, swap 0B. Предыдущие этапы: [clean bootstrap](amd64-clean-bootstrap-2026-10-03.md), [clean deploy + verify](amd64-clean-deploy-verify-2026-10-03.md). Этот этап выполнен агентом через SSH на той же VM; IP/credentials исключены.

## Tested revision

VM branch fix/amd64-bootstrap, exact SHA `6c611c46862061caba371b27b9df2e062f2753be`. Checkout на VM не обновлялся: git pull, checkout, fetch или reset не выполнялись. Remote documentation commits f319209e и 6d01d498 не применялись к VM; локальная документация создаётся поверх `6d01d4982edb9249286772cd4987746dd161739b`. SHA после сценария тот же, рабочее дерево чистое. main не меняется.

## Initial state

Перед запуском 2026-10-03T18:59:06+00:00: node vm-928254 Ready, все 17 pods Running/Ready, RESTARTS 0. HTTPRoute demo-route v1=100/v2=0; ConfigMap APP_FORCE_ERRORS=false. Read-only SQLite SELECT release подтвердил status=stable, weights=100/0, reconcile_required=false. Обычный Gateway GET /demo с Host trafficops.local вернул HTTP 200/v1 (request_id b5fcdf20-a32b-4533-b1d4-e6918905e97d).

```text
2026-10-03T18:59:06+00:00
fix/amd64-bootstrap
6c611c46862061caba371b27b9df2e062f2753be
NAME        STATUS   ROLES           AGE   VERSION
vm-928254   Ready    control-plane   24m   v1.36.5
NAMESPACE              NAME                                                   READY   STATUS    RESTARTS   AGE
envoy-gateway-system   envoy-gateway-6fbfccc98d-fqglk                         1/1     Running   0          15m
envoy-gateway-system   envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running   0          15m
kube-flannel           kube-flannel-ds-xcfgs                                  1/1     Running   0          24m
kube-system            coredns-589f44dc88-jqt2h                               1/1     Running   0          24m
kube-system            coredns-589f44dc88-kx88r                               1/1     Running   0          24m
kube-system            etcd-vm-928254                                         1/1     Running   0          24m
kube-system            kube-apiserver-vm-928254                               1/1     Running   0          24m
kube-system            kube-controller-manager-vm-928254                      1/1     Running   0          24m
kube-system            kube-proxy-8b98x                                       1/1     Running   0          24m
kube-system            kube-scheduler-vm-928254                               1/1     Running   0          24m
observability          fluentd-jg726                                          1/1     Running   0          15m
observability          kube-state-metrics-757668c8cd-pzslc                    1/1     Running   0          15m
observability          node-exporter-rjwpj                                    1/1     Running   0          15m
observability          prometheus-744757757d-tjq4r                            1/1     Running   0          15m
trafficops             demo-v1-79c45b95f4-trpkh                               1/1     Running   0          16m
trafficops             demo-v2-5cbb4bdbc7-b84mw                               1/1     Running   0          16m
trafficops             trafficops-controller-54ffbd7dd4-r82d7                 1/1     Running   0          15m
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"gateway.networking.k8s.io/v1","kind":"HTTPRoute","metadata":{"annotations":{},"name":"demo-route","namespace":"trafficops"},"spec":{"parentRefs":[{"name":"trafficops"}],"rules":[{"backendRefs":[{"name":"demo-v1","port":8080,"weight":100},{"name":"demo-v2","port":8080,"weight":0}],"matches":[{"path":{"type":"PathPrefix","value":"/demo"}}]}]}}
  creationTimestamp: "2026-10-03T18:43:18Z"
  generation: 1
  name: demo-route
  namespace: trafficops
  resourceVersion: "1557"
  uid: 4614997b-c719-4778-8997-8cd62eed47f0
spec:
  parentRefs:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: trafficops
  rules:
  - backendRefs:
    - group: ""
      kind: Service
      name: demo-v1
      port: 8080
      weight: 100
    - group: ""
      kind: Service
      name: demo-v2
      port: 8080
      weight: 0
    matches:
    - path:
        type: PathPrefix
        value: /demo
status:
  parents:
  - conditions:
    - lastTransitionTime: "2026-10-03T18:43:18Z"
      message: Route is accepted
      observedGeneration: 1
      reason: Accepted
      status: "True"
      type: Accepted
    - lastTransitionTime: "2026-10-03T18:43:18Z"
      message: Resolved all the Object references for the Route
      observedGeneration: 1
      reason: ResolvedRefs
      status: "True"
      type: ResolvedRefs
    controllerName: gateway.envoyproxy.io/gatewayclass-controller
    parentRef:
      group: gateway.networking.k8s.io
      kind: Gateway
      name: trafficops
apiVersion: v1
data:
  APP_FORCE_ERRORS: "false"
kind: ConfigMap
metadata:
  creationTimestamp: "2026-10-03T18:42:50Z"
  name: demo-v2-config
  namespace: trafficops
  resourceVersion: "1171"
  uid: 55eef85c-e4aa-4372-948f-37ba8ca68af5
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.7Gi       239Mi       4.1Mi       2.3Gi       2.2Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.2G   52G   9% /
```

## Scenario command

```bash
date -Is
set -o pipefail
make verify-scenario 2>&1 | tee ~/trafficops-clean-scenario.log
scenario_exit=${PIPESTATUS[0]}
echo "SCENARIO_EXIT=$scenario_exit"
date -Is
```

Start: 2026-10-03T18:59:22+00:00 (21:59:22 MSK).
End: 2026-10-03T19:01:42+00:00 (22:01:42 MSK).
**SCENARIO_EXIT=2** — GNU make сообщает 2 при неуспешном recipe; scripts/verify-scenario.py завершился 1.

Полный transcript (stderr ERROR расположен раньше буферизованного stdout):

```text
./scripts/verify-scenario.py
ERROR: GET /api/overview returned HTTP 503
Resetting demo-v2 error switch; waiting 130 seconds for ConfigMap projection.
Running healthy canary with 20 requests/s for at most 180 seconds.
make: *** [Makefile:16: verify-scenario] Error 1
```

Raw transcript сохранён на VM /root/trafficops-clean-scenario.log. Сценарий не перезапускался.

## Healthy canary

**Не подтверждён полностью.** Старт canary succeeded, controller journal показывает фактические веса v1=90/v2=10, started_at=1791054096.7467706. Серия 20 requests/s с лимитом 180 seconds завершена cleanup после примерно 6.13 секунд: sent=123, failed=0, run_id run-32bd16e9af5c4378.

Prometheus после остановки подтвердил **13 запросов v2**, 0 v2 5xx, source timestamp 1791054235.848 (sample age примерно 0.971 секунды на момент capture). Это cumulative counter, не 60-second increase и не достаточное policy evidence. v2 реально получил около 10.6% от 123 запросов серии; сравнение относится к этой исходно первой серии, но не заменяет подтверждение полного окна canary.

Первая canary-check: state=unknown, breaches=0, reason="Prometheus sample is missing or ambiguous". Safe observe decision не достигнут; полное окно 60 seconds и минимум 30 запросов не достигнуты. Затем первый GET /api/overview при wait_for_healthy вернул 503, и сценарий прекратил основной поток.

Policy из read-only post overview: window_seconds=60, min_requests=30, error_threshold=0.05, required_breaches=2, check_seconds=10, max_sample_age_seconds=30.

## Complete v2

**Не выполнено.** release-complete не вызывался; переход 0/100 и Gateway v2 после завершения релиза не проверены.

## Manual rollback

Основная стадия manual rollback после complete-v2 **не достигнута**. Отдельно встроенный finally cleanup сценария выполнил штатный controller API rollback: journal release-rollback succeeded, reason=manual rollback, weights=100/0, confirmed_version=v1. Это подтверждение восстановления после failed сценария, не PASS полной стадии D.

## Fault injection

**Не выполнялась.** enabled=true не вызывался, ConfigMap остался false. v2 5xx=0 по диагностическому cumulative PromQL; этот ноль не свидетельствует об успешной проверке fault injection.

## Automatic rollback

**Не выполнялся и не подтверждён.** Threshold breach, две последовательные breach checks и automatic rollback не достигнуты. Единственная canary-check unknown/breaches=0. Final rollback имеет reason=manual rollback от встроенного cleanup, не automatic rollback.

## Operation journal

Read-only SQLite через kubectl exec controller; connection URI mode=ro. Выбраны только operations начиная с запуска и state keys release/traffic/incident. Sessions, CSRF, passwords/Secret contents не читались и не сохранялись. Последовательность: errors false → traffic start → release start 90/10 → unknown metric check → stop traffic → errors false → cleanup rollback 100/0. Logout HTTP 200 подтверждён Envoy access record.

```json
{"id": "b49007b4ae5840b7aa4b6e38685aafca", "kind": "incident-errors", "status": "succeeded", "created": 1791053965.6685166, "updated": 1791053965.6811457, "reason": null, "details": {"enabled": false, "intent": "persisted", "note": "v2 receives the ConfigMap through the fixed pod mount"}}
{"id": "295fe61ef9af407ba620c8878c6824b9", "kind": "traffic-start", "status": "succeeded", "created": 1791054095.6912568, "updated": 1791054101.8229206, "reason": null, "details": {"status": "stopped", "run_id": "run-32bd16e9af5c4378", "rate": 20, "duration": 180, "path": "/demo", "sent": 123, "failed": 0, "started_at": 1791054095.6887834, "finished_at": 1791054101.8207734}}
{"id": "2acbff123e40432bb3c73695674302f6", "kind": "release-start", "status": "succeeded", "created": 1791054095.6997151, "updated": 1791054096.749234, "reason": null, "details": {"weights": {"v1": 90, "v2": 10}, "intent": "persisted", "started_at": 1791054096.7467706}}
{"id": "ab1871384f7c4610a7f049297b2fd188", "kind": "canary-check", "status": "succeeded", "created": 1791054097.9141243, "updated": 1791054097.9141243, "reason": "Prometheus sample is missing or ambiguous", "details": {"metrics": {"state": "unknown", "breaches": 0, "reason": "Prometheus sample is missing or ambiguous"}, "checked_at": 1791054097.9141219}}
{"id": "b64180e377e64793b6bdc965878ccc9e", "kind": "incident-errors", "status": "succeeded", "created": 1791054101.8278623, "updated": 1791054101.8398707, "reason": null, "details": {"enabled": false, "intent": "persisted", "note": "v2 receives the ConfigMap through the fixed pod mount"}}
{"id": "c11570a5afda49d9a68f734db969a06e", "kind": "release-rollback", "status": "succeeded", "created": 1791054101.844729, "updated": 1791054102.8960032, "reason": "manual rollback", "details": {"route": {"v1": 100, "v2": 0}, "intent": "persisted", "weights": {"v1": 100, "v2": 0}, "confirmed_version": "v1", "reason": "manual rollback"}}
SAFE_STATE
{"key": "release", "value": {"status": "rolled-back", "weights": {"v1": 100, "v2": 0}, "reason": "manual rollback", "rolled_back_at": 1791054102.8931215, "reconcile_required": false}}
{"key": "traffic", "value": {"status": "stopped", "run_id": "run-32bd16e9af5c4378", "rate": 20, "duration": 180, "path": "/demo", "sent": 123, "failed": 0, "started_at": 1791054095.6887834, "finished_at": 1791054101.8207734}}
```

## Read-only diagnosis

Envoy access log локализует ошибку GET /api/overview: HTTP 503, response_flags=UC, response_code_details=upstream_reset_before_response_started{connection_termination}, duration=0, route trafficops-panel. Это reset upstream-соединения до ответа; **почему upstream закрыл соединение, не установлено**. Ошибка не доказана как следствие Prometheus unknown decision. Controller logs --since=5m --tail=100 были пустыми; controller pod не перезапускался. Поздний GET overview возвращает HTTP 200, services/metrics available, reconcile_required=false. Runtime вручную не исправлялся.

```json
{"start_time": "2026-10-03T19:01:35.697Z", "method": "POST", "x-envoy-origin-path": "/api/release/start", "response_code": 200, "response_code_details": "via_upstream", "response_flags": "-", "duration": 1053, "route_name": "httproute/trafficops/trafficops-panel/rule/0/match/0/*", "x-request-id": "50cdc44d-3e68-45c1-bbac-5515776e909e"}
{"start_time": "2026-10-03T19:01:41.814Z", "method": "GET", "x-envoy-origin-path": "/api/overview", "response_code": 503, "response_code_details": "upstream_reset_before_response_started{connection_termination}", "response_flags": "UC", "duration": 0, "route_name": "httproute/trafficops/trafficops-panel/rule/0/match/0/*", "x-request-id": "fa5547e8-4050-4259-842e-0f0cdd9852d8"}
{"start_time": "2026-10-03T19:01:41.843Z", "method": "POST", "x-envoy-origin-path": "/api/release/rollback", "response_code": 200, "response_code_details": "via_upstream", "response_flags": "-", "duration": 1054, "route_name": "httproute/trafficops/trafficops-panel/rule/0/match/0/*", "x-request-id": "7d77c12d-b72d-4453-914f-5b6abc859936"}
{"start_time": "2026-10-03T19:01:42.899Z", "method": "POST", "x-envoy-origin-path": "/api/logout", "response_code": 200, "response_code_details": "via_upstream", "response_flags": "-", "duration": 3, "route_name": "httproute/trafficops/trafficops-panel/rule/0/match/0/*", "x-request-id": "d27483d6-386b-46e3-ae62-7edfaefbe1cb"}
```

```text
POST_OVERVIEW {"http_status": 200, "release": {"status": "rolled-back", "weights": {"v1": 100, "v2": 0}, "reason": "manual rollback", "rolled_back_at": 1791054102.8931215, "reconcile_required": false}, "services_status": "available", "weights": {"v1": 100, "v2": 0}, "metrics_status": "available", "traffic": {"status": "stopped", "run_id": "run-32bd16e9af5c4378", "rate": 20, "duration": 180, "path": "/demo", "sent": 123, "failed": 0, "started_at": 1791054095.6887834, "finished_at": 1791054101.8207734}, "policy": {"window_seconds": 60, "min_requests": 30, "error_threshold": 0.05, "required_breaches": 2, "check_seconds": 10, "max_sample_age_seconds": 30}}
```

Read-only PromQL выполнен из controller pod через urllib к существующему Prometheus Service, без изменения config и без установки компонентов:

```json
{"query": "sum(trafficops_http_requests_total{version=\"v2\"})", "capture_time": 1791054236.814073, "payload": {"status": "success", "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1791054236.813, "13"]}]}}}
{"query": "sum(trafficops_http_requests_total{version=\"v2\",status=~\"5..\"}) or vector(0)", "capture_time": 1791054236.8167088, "payload": {"status": "success", "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1791054236.816, "0"]}]}}}
{"query": "max(timestamp(trafficops_http_requests_total{version=\"v2\"}))", "capture_time": 1791054236.8189979, "payload": {"status": "success", "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1791054236.818, "1791054235.848"]}]}}}
```

Предложение для отдельного исправления: исследовать закрытие Envoy→controller upstream-соединения (в том числе keep-alive timing); после подтверждения причины исправить её и отдельно рассмотреть ограниченный retry только идемпотентного GET overview в scenario, с явным журналированием transient failure и сохранением общего deadline. Это гипотеза/направление, не реализованное исправление и не установленная корневая причина. Retry POST и сокрытие failed attempts не предлагаются.

## Cleanup

Встроенный finally сценария штатно остановил traffic, выключил v2 errors, выполнил controller rollback и logout; CLEANUP ERROR отсутствует. Агент не выполнял дополнительных управляющих команд. Final state rolled-back, reason=manual rollback, reconcile_required=false; weights=100/0, APP_FORCE_ERRORS=false. После сценария обычный Gateway GET /demo HTTP 200/v1 (request_id 05fe1f60-ac0d-4aaf-9b50-9a4bdb035cfa), /healthz HTTP 200/status ok.

Все 17 pods Running/Ready, RESTARTS 0, node Ready; нет текущих CrashLoopBackOff. Failed systemd units=0. Полный post-scenario snapshot:

```text
2026-10-03T19:02:43+00:00
NAME        STATUS   ROLES           AGE   VERSION
vm-928254   Ready    control-plane   28m   v1.36.5
NAMESPACE              NAME                                                   READY   STATUS    RESTARTS   AGE
envoy-gateway-system   envoy-gateway-6fbfccc98d-fqglk                         1/1     Running   0          19m
envoy-gateway-system   envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running   0          19m
kube-flannel           kube-flannel-ds-xcfgs                                  1/1     Running   0          28m
kube-system            coredns-589f44dc88-jqt2h                               1/1     Running   0          28m
kube-system            coredns-589f44dc88-kx88r                               1/1     Running   0          28m
kube-system            etcd-vm-928254                                         1/1     Running   0          28m
kube-system            kube-apiserver-vm-928254                               1/1     Running   0          28m
kube-system            kube-controller-manager-vm-928254                      1/1     Running   0          28m
kube-system            kube-proxy-8b98x                                       1/1     Running   0          28m
kube-system            kube-scheduler-vm-928254                               1/1     Running   0          28m
observability          fluentd-jg726                                          1/1     Running   0          19m
observability          kube-state-metrics-757668c8cd-pzslc                    1/1     Running   0          19m
observability          node-exporter-rjwpj                                    1/1     Running   0          19m
observability          prometheus-744757757d-tjq4r                            1/1     Running   0          19m
trafficops             demo-v1-79c45b95f4-trpkh                               1/1     Running   0          19m
trafficops             demo-v2-5cbb4bdbc7-b84mw                               1/1     Running   0          19m
trafficops             trafficops-controller-54ffbd7dd4-r82d7                 1/1     Running   0          19m
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"gateway.networking.k8s.io/v1","kind":"HTTPRoute","metadata":{"annotations":{},"name":"demo-route","namespace":"trafficops"},"spec":{"parentRefs":[{"name":"trafficops"}],"rules":[{"backendRefs":[{"name":"demo-v1","port":8080,"weight":100},{"name":"demo-v2","port":8080,"weight":0}],"matches":[{"path":{"type":"PathPrefix","value":"/demo"}}]}]}}
  creationTimestamp: "2026-10-03T18:43:18Z"
  generation: 3
  name: demo-route
  namespace: trafficops
  resourceVersion: "3949"
  uid: 4614997b-c719-4778-8997-8cd62eed47f0
spec:
  parentRefs:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: trafficops
  rules:
  - backendRefs:
    - group: ""
      kind: Service
      name: demo-v1
      port: 8080
      weight: 100
    - group: ""
      kind: Service
      name: demo-v2
      port: 8080
      weight: 0
    matches:
    - path:
        type: PathPrefix
        value: /demo
status:
  parents:
  - conditions:
    - lastTransitionTime: "2026-10-03T19:01:41Z"
      message: Route is accepted
      observedGeneration: 3
      reason: Accepted
      status: "True"
      type: Accepted
    - lastTransitionTime: "2026-10-03T19:01:41Z"
      message: Resolved all the Object references for the Route
      observedGeneration: 3
      reason: ResolvedRefs
      status: "True"
      type: ResolvedRefs
    controllerName: gateway.envoyproxy.io/gatewayclass-controller
    parentRef:
      group: gateway.networking.k8s.io
      kind: Gateway
      name: trafficops
apiVersion: v1
data:
  APP_FORCE_ERRORS: "false"
kind: ConfigMap
metadata:
  creationTimestamp: "2026-10-03T18:42:50Z"
  name: demo-v2-config
  namespace: trafficops
  resourceVersion: "1171"
  uid: 55eef85c-e4aa-4372-948f-37ba8ca68af5
=== RESOURCES ===
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.6Gi       270Mi       4.1Mi       2.3Gi       2.2Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.2G   52G   9% /
=== FAILED SYSTEMD ===
  UNIT LOAD ACTIVE SUB DESCRIPTION

0 loaded units listed.
=== RECENT OOM ===
=== CONTROLLER LOGS ===
```

## Resources

После сценария RAM total 3.8Gi, used 1.6Gi, available 2.2Gi, swap 0B. Disk 58G, used 5.2G, available 52G (9%). journalctl -k за последние 20 минут с фильтром out of memory|oom-kill|killed process не выдал записей. Это ограниченная проверка журнала и текущего состояния, не нагрузочный soak.

## Manual fixes

None. Rollback/errors false/stop/logout выполнены самим finally существующего scenario; дополнительных ручных runtime fixes не было.

## Result

**FAIL.** Первый полный AMD64 scenario завершился с make exit 2 из-за GET /api/overview HTTP 503. Canary стартовал и получил реальный трафик, но здоровое полное окно, complete-v2, основная manual rollback стадия, fault injection и automatic rollback не подтверждены. Успешный cleanup и здоровое final state не заменяют PASS сценария.

## Scope

- Повторный bootstrap ещё не проверен.
- Повторный deploy ещё не проверен.
- Security negative tests ещё не выполнялись на AMD64.
- UI руками в этом этапе не проверялся.
- main не изменялся; merge не выполнялся.
- Acceptance/README/passport не менялись.
- Functional code changes: none.
- После failure выполнена только read-only диагностика и documentation evidence; сценарий повторно не запускался.

