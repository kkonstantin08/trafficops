# TrafficOps AMD64 live security negative tests — 3 октября 2026

## Environment

Выполнено агентом через SSH на той же VM Ubuntu 24.04.4 LTS, amd64/x86_64, 4 CPU, MemTotal 4015132 KiB, swap 0B. Предыдущие evidence: [clean bootstrap](amd64-clean-bootstrap-2026-10-03.md), [clean deploy/verify](amd64-clean-deploy-verify-2026-10-03.md), [passing scenario и controller fix](amd64-scenario-fix-2026-10-03.md), [idempotence](amd64-idempotence-2026-10-03.md).

Все HTTP requests выполнены через настоящий Gateway NodePort/controller route, origin `http://[REDACTED_VM]:30080`; IP вычислялся внутри VM процесса из node InternalIP. Использован stdlib Python urllib.request/http.cookies, без новых зависимостей/scanners и без browser automation. Request Host соответствует вычисленному NodePort origin; обычный panel route не требует отдельного hostname. Ни одного прямого Service request вместо Gateway в security suite не было.

## Tested revision

Exact VM functional SHA `0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f`, working tree clean до и после. Remote documentation-only commits, включая `c123ef007701f64142e06ef8cf6d1359f275c900`, на VM не применялись; fetch/checkout/pull/reset на VM не выполнялись. Локальная documentation branch fix/amd64-bootstrap синхронизирована с c123ef00 перед добавлением только данного evidence.

## Pre-state

Suite start 2026-10-03T20:28:40.588063Z; end 20:28:58.060639Z. Node vm-928254 Ready, UID `dccf69fa-f8c5-480a-adfa-f1baf3dcab10`, created 18:34:10Z. Route UID `4614997b-c719-4778-8997-8cd62eed47f0`, weights 100/0; APP_FORCE_ERRORS=false. Release rolled-back, reconcile_required=false, traffic stopped. Все 17 long-running pods Running/Ready, restarts 0; штатный retention Job Completed.

До HTTP tests снят safe read-only snapshot: route UID/weights, errors ConfigMap, pod names/UID/phase/readiness/restarts, полный operational release/traffic state, count и отсортированный набор operation IDs. Read-only SQLite mode=ro: только operations IDs и state keys release/traffic, без sessions/Secret/password hash. Сравнение выполнялось после **каждого** request, включая rejected inputs и session lifecycle.

Suite был одним bounded запуском, 25 HTTP requests, без retries. При неожиданном status/detail или operational state change script должен был немедленно остановиться и сохранить FAIL; повтор до случайного PASS и исправление кода не выполнялись. Итог **SECURITY_EXIT=0**.

## Public surface

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| public / (GET /) | 200 | 200 | PASS |
| public /healthz (GET /healthz) | 200 | 200 | PASS |
| public /api/session (GET /api/session) | 200 | 200 | PASS |
| public /docs (GET /docs) | 404 | 404 | PASS |
| public /redoc (GET /redoc) | 404 | 404 | PASS |
| public /openapi.json (GET /openapi.json) | 404 | 404 | PASS |

Фактические результаты приведены в таблице. `/`, `/healthz`, `/api/session` — 200; unauthenticated session=false. `/docs`, `/redoc`, `/openapi.json` — 404.

## Authentication

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| login missing Origin (POST /api/login) | 403 | 403 | PASS |
| login wrong Origin (POST /api/login) | 403 | 403 | PASS |
| login wrong password (POST /api/login) | 401 | 401 | PASS |
| login oversized password (POST /api/login) | 422 | 422 | PASS |
| valid login (POST /api/login) | 200 | 200 | PASS |

Login без Origin и с Origin `http://evil.example` — 403, detail соответствует `request Origin is not allowed`. Correct Origin + гарантированно неверный пароль — 401, detail `invalid password`. Password 257 symbols — 422; validation response body с input не выводился и не сохранялся. Это четыре bounded negative cases, не brute force.

Один valid login — 200/authenticated=true, cookie и CSRF присутствуют. Реальный пароль прочитан только в VM test process из ~/.config/trafficops/admin-password, не выводился, не передавался в command-line arguments и не записывался в test logs/evidence.

## Cookie properties

Проверено только наличие и attributes: HttpOnly=true, SameSite=strict, Path=/, Secure=false; cookie_present=true, csrf_present=true. Secure=false ожидаемо для текущего HTTP стенда и не считается regression. Cookie/session token и CSRF значения хранились только в памяти test process; Set-Cookie целиком не сохранялся.

## Session enforcement

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| mutation without session (POST /api/traffic/start) | 401 | 401 | PASS |
| valid logout (POST /api/logout) | 200 | 200 | PASS |
| old cookie replay after logout (POST /api/traffic/start) | 401 | 401 | PASS |
| session after logout (GET /api/session) | 200 | 200 | PASS |

Cookie-less POST /api/traffic/start с корректным Origin и bounded payload rate=1/duration=1/path=/demo — 401/login required; traffic не запускался. После logout старый cookie вручную повторно передан из памяти процесса вместе со старым CSRF — 401/login required. Это server-side invalidation, а не только удаление cookie клиентом. Subsequent cookie-less GET /api/session — 200/authenticated=false.

## Origin enforcement

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| authenticated wrong Origin (POST /api/traffic/start) | 403 | 403 | PASS |
| authenticated missing Origin (POST /api/traffic/start) | 403 | 403 | PASS |

Login missing/wrong Origin — 403. Authenticated POST /api/traffic/start с правильным CSRF, но wrong Origin — 403; дополнительно authenticated missing Origin — 403. В обоих cases detail соответствует Origin enforcement, state unchanged.

## CSRF enforcement

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| missing CSRF (POST /api/traffic/start) | 403 | 403 | PASS |
| invalid CSRF (POST /api/traffic/start) | 403 | 403 | PASS |

Authenticated POST /api/traffic/start с правильным Origin, missing CSRF — 403; invalid-test-token — 403. Detail соответствует `CSRF token is missing or invalid`; traffic remained stopped. Валидный traffic start с одновременно правильными Origin/session/CSRF не отправлялся.

## Input bounds

| Test | Expected | Actual | Result |
| --- | --- | --- | --- |
| arbitrary URL (POST /api/traffic/start) | 422 | 422 | PASS |
| arbitrary path (POST /api/traffic/start) | 422 | 422 | PASS |
| rate21 (POST /api/traffic/start) | 422 | 422 | PASS |
| duration181 (POST /api/traffic/start) | 422 | 422 | PASS |
| weight -1 (POST /api/release/weight) | 422 | 422 | PASS |
| weight 101 (POST /api/release/weight) | 422 | 422 | PASS |

С легитимной session, Origin и CSRF отклонены до управляющего действия: arbitrary URL http://example.com, arbitrary path /etc/passwd, rate=21, duration=181, release weight=-1 и 101 — все 422. Валидный release weight не отправлялся. Эти inputs не запускали traffic/release/fault или pod deletion; operation journal не изменился.

## Side effects

**None.** Полные safe operational snapshots pre/post одинаковы; после каждого из 25 requests operational_state_unchanged=true. После post make verify snapshot также одинаковый. Route 100/0, errors=false, traffic stopped, release rolled-back, reconcile_required=false. Route UID и все pod UID/readiness/restart counts сохранены.

Operations before 32 → after 32 → after verify 32; набор всех старых IDs идентичен, новых release/traffic/incident operations нет. Login/logout изменяют только session lifecycle; session table contents не читались. Старый traffic failed=95 относится к предыдущему fault scenario и не вырос во время security tests.

## Runtime health

После suite выполнен один штатный make verify (с pipefail/tee, exit из PIPESTATUS[0]), 2026-10-03T20:29:12Z → 20:29:19Z. **POST_SECURITY_VERIFY_EXIT=0/PASS**. Gateway HTTP 200/v1 marker `verify-97757209637b4cc4aa13fe968e82b793` найден Fluentd within 30s; fresh Prometheus samples для пяти jobs up и v1 HTTP 200 counter; panel/controller 200/200. Release/traffic/route/errors/journal/pod identity после verify сохранены.

Node Ready, все 17 long-running pods Ready, restarts 0; no current CrashLoopBackOff/ImagePullBackOff/Pending/NotReady. RAM 3.8Gi total/1.8Gi used/2.0Gi available, swap 0B; disk 58G/5.4G used/52G available. Failed systemd units 0. Kernel journal 15min: OOM matches 0; controller logs 15min пусты. Runtime transcript ниже.

## Secrets handling

- Password not printed.
- Cookie/session token not printed.
- CSRF not printed.
- Secret contents not read; password hash и sessions table contents не читались.
- Public evidence sanitized; IP заменён на REDACTED_VM.
- Только status/detail_matches/authenticated/attribute booleans и safe state публикуются; response bodies login/validation и headers с token values не публикуются.

## Result

**PASS.** Все 25 expected outcomes совпали; Origin/CSRF reason checked, cookie flags проверены, replay старой session отклонён после logout. Rejected requests не вызвали operational side effects; post verify PASS. Functional code changes: none. Runtime fixes: none.

## Scope

- Это не penetration test; проверен заданный bounded набор endpoint cases, не все возможные attacks/endpoints.
- TLS не тестируется: current local deployment HTTP.
- RBAC escalation отдельно не выполнялась.
- Ручная visual UI проверка ещё не выполнена.
- Acceptance/README/passport ещё не обновлялись.
- main не merge; remote main остаётся `20e5d247b4b044cec80f1a3c3f03abd940c3574c`.
- Bootstrap/deploy/full scenario не запускались; VM checkout не обновлялся.

## Safe state comparison

```json
{
  "node": {
    "name": "vm-928254",
    "uid": "dccf69fa-f8c5-480a-adfa-f1baf3dcab10",
    "creationTimestamp": "2026-10-03T18:34:10Z"
  },
  "route_uid": "4614997b-c719-4778-8997-8cd62eed47f0",
  "weights": {
    "demo-v1": 100,
    "demo-v2": 0
  },
  "errors": "false",
  "state": {
    "release": {
      "status": "rolled-back",
      "weights": {
        "v1": 100,
        "v2": 0
      },
      "reason": "manual rollback",
      "rolled_back_at": 1791056626.5692399,
      "reconcile_required": false
    },
    "traffic": {
      "status": "stopped",
      "run_id": "run-681dea337e754848",
      "rate": 20,
      "duration": 180,
      "path": "/demo",
      "sent": 1534,
      "failed": 95,
      "started_at": 1791056549.8046007,
      "finished_at": 1791056626.5030522
    }
  },
  "operations_count_before": 32,
  "operations_count_after": 32,
  "operation_ids_unchanged": true,
  "full_safe_state_unchanged": true,
  "after_verify_unchanged": true,
  "cookie_properties": {
    "cookie_present": true,
    "csrf_present": true,
    "HttpOnly": true,
    "SameSite": "strict",
    "Path": "/",
    "Secure": false
  }
}
```

Pod identity before = after = after verify:

| Namespace | Pod | UID | Phase | Restarts |
| --- | --- | --- | --- | --- |
| envoy-gateway-system | envoy-gateway-6fbfccc98d-fqglk | 1c5d954a-e408-470e-977e-e5554a80ec47 | Running | 0 |
| envoy-gateway-system | envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f | 673c3bc8-c88f-4eb6-85fc-8460297d1104 | Running | 0 |
| kube-flannel | kube-flannel-ds-xcfgs | 805fa020-5aee-41cc-bb4f-7403e5a8aeab | Running | 0 |
| kube-system | coredns-589f44dc88-jqt2h | a9cb2fcb-b150-47aa-a5f9-43e9e45c188f | Running | 0 |
| kube-system | coredns-589f44dc88-kx88r | 141b3887-fdb8-44a4-bbb5-a42f779c6dfe | Running | 0 |
| kube-system | etcd-vm-928254 | c74f4184-9177-439f-8343-ea950fdeb048 | Running | 0 |
| kube-system | kube-apiserver-vm-928254 | 74a10084-87fb-4bc3-b995-bc3067dac122 | Running | 0 |
| kube-system | kube-controller-manager-vm-928254 | b127225b-9c7a-435f-aa82-e1501a6ac8f1 | Running | 0 |
| kube-system | kube-proxy-8b98x | 8383b18e-6866-4a98-a847-257f78894d5b | Running | 0 |
| kube-system | kube-scheduler-vm-928254 | dd300406-6121-453d-9695-6b2a46774277 | Running | 0 |
| observability | fluentd-jg726 | 99913e8e-0231-4fad-9a2d-39078c97f0da | Running | 0 |
| observability | fluentd-log-retention-29850977-cdbrh | f2f13e09-fc57-4a12-8652-ea84bf3b376e | Succeeded | 0 |
| observability | kube-state-metrics-757668c8cd-pzslc | 148ad036-a38a-4a6d-acbf-11e4442b081f | Running | 0 |
| observability | node-exporter-rjwpj | 2376b823-fc56-4ae2-9d74-4bb5c8b724df | Running | 0 |
| observability | prometheus-744757757d-tjq4r | 49da19e5-01d1-4821-87f5-6a359835fe95 | Running | 0 |
| trafficops | demo-v1-79c45b95f4-trpkh | 2d34502f-1fd8-412c-9df3-85107e31d6c9 | Running | 0 |
| trafficops | demo-v2-5cbb4bdbc7-b84mw | 960bca43-94a6-4be8-9366-587f99631a52 | Running | 0 |
| trafficops | trafficops-controller-6d99494c76-pjqxg | 4be0a21a-f412-48ca-a01e-338c245df8fc | Running | 0 |

## Per-request records

```json
[
  {
    "test": "public /",
    "method": "GET",
    "path": "/",
    "expected": 200,
    "actual": 200,
    "time": 1791059320.626064,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "public /healthz",
    "method": "GET",
    "path": "/healthz",
    "expected": 200,
    "actual": 200,
    "time": 1791059321.2796078,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "public /api/session",
    "method": "GET",
    "path": "/api/session",
    "expected": 200,
    "actual": 200,
    "time": 1791059321.9188683,
    "result": "PASS",
    "authenticated": false,
    "operational_state_unchanged": true
  },
  {
    "test": "public /docs",
    "method": "GET",
    "path": "/docs",
    "expected": 404,
    "actual": 404,
    "time": 1791059322.5624366,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "public /redoc",
    "method": "GET",
    "path": "/redoc",
    "expected": 404,
    "actual": 404,
    "time": 1791059323.2012928,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "public /openapi.json",
    "method": "GET",
    "path": "/openapi.json",
    "expected": 404,
    "actual": 404,
    "time": 1791059323.8180926,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "login missing Origin",
    "method": "POST",
    "path": "/api/login",
    "expected": 403,
    "actual": 403,
    "time": 1791059324.4511416,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "login wrong Origin",
    "method": "POST",
    "path": "/api/login",
    "expected": 403,
    "actual": 403,
    "time": 1791059325.0597725,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "login wrong password",
    "method": "POST",
    "path": "/api/login",
    "expected": 401,
    "actual": 401,
    "time": 1791059326.181336,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "login oversized password",
    "method": "POST",
    "path": "/api/login",
    "expected": 422,
    "actual": 422,
    "time": 1791059326.8225236,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "valid login",
    "method": "POST",
    "path": "/api/login",
    "expected": 200,
    "actual": 200,
    "time": 1791059327.9840367,
    "result": "PASS",
    "authenticated": true,
    "operational_state_unchanged": true
  },
  {
    "test": "mutation without session",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 401,
    "actual": 401,
    "time": 1791059328.6182375,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "authenticated wrong Origin",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 403,
    "actual": 403,
    "time": 1791059329.2624013,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "authenticated missing Origin",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 403,
    "actual": 403,
    "time": 1791059329.9054596,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "missing CSRF",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 403,
    "actual": 403,
    "time": 1791059330.5181177,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "invalid CSRF",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 403,
    "actual": 403,
    "time": 1791059331.1601553,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "arbitrary URL",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 422,
    "actual": 422,
    "time": 1791059331.808188,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "arbitrary path",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 422,
    "actual": 422,
    "time": 1791059332.4620326,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "rate21",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 422,
    "actual": 422,
    "time": 1791059333.1128187,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "duration181",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 422,
    "actual": 422,
    "time": 1791059333.7478073,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "weight -1",
    "method": "POST",
    "path": "/api/release/weight",
    "expected": 422,
    "actual": 422,
    "time": 1791059334.3611884,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "weight 101",
    "method": "POST",
    "path": "/api/release/weight",
    "expected": 422,
    "actual": 422,
    "time": 1791059335.009186,
    "result": "PASS",
    "operational_state_unchanged": true
  },
  {
    "test": "valid logout",
    "method": "POST",
    "path": "/api/logout",
    "expected": 200,
    "actual": 200,
    "time": 1791059335.6558506,
    "result": "PASS",
    "authenticated": false,
    "operational_state_unchanged": true
  },
  {
    "test": "old cookie replay after logout",
    "method": "POST",
    "path": "/api/traffic/start",
    "expected": 401,
    "actual": 401,
    "time": 1791059336.2600236,
    "result": "PASS",
    "detail_matches": true,
    "operational_state_unchanged": true
  },
  {
    "test": "session after logout",
    "method": "GET",
    "path": "/api/session",
    "expected": 200,
    "actual": 200,
    "time": 1791059336.8598576,
    "result": "PASS",
    "authenticated": false,
    "operational_state_unchanged": true
  }
]
```

## Post verify transcript

```text
./scripts/verify.sh
NAME        STATUS   ROLES           AGE    VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   115m   v1.36.5   [REDACTED_VM]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       105m
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [REDACTED_VM]   True         105m

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     105m
httproute.gateway.networking.k8s.io/trafficops-panel               105m
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-97757209637b4cc4aa13fe968e82b793
Fluentd log verified within 30 seconds: request_id verify-97757209637b4cc4aa13fe968e82b793, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200
POST_SECURITY_VERIFY_EXIT=0
```

## Runtime snapshot

```text
$ kubectl get nodes
NAME        STATUS   ROLES           AGE    VERSION
vm-928254   Ready    control-plane   115m   v1.36.5

$ kubectl get pods -A
NAMESPACE              NAME                                                   READY   STATUS      RESTARTS   AGE
envoy-gateway-system   envoy-gateway-6fbfccc98d-fqglk                         1/1     Running     0          106m
envoy-gateway-system   envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running     0          106m
kube-flannel           kube-flannel-ds-xcfgs                                  1/1     Running     0          115m
kube-system            coredns-589f44dc88-jqt2h                               1/1     Running     0          115m
kube-system            coredns-589f44dc88-kx88r                               1/1     Running     0          115m
kube-system            etcd-vm-928254                                         1/1     Running     0          115m
kube-system            kube-apiserver-vm-928254                               1/1     Running     0          115m
kube-system            kube-controller-manager-vm-928254                      1/1     Running     0          115m
kube-system            kube-proxy-8b98x                                       1/1     Running     0          115m
kube-system            kube-scheduler-vm-928254                               1/1     Running     0          115m
observability          fluentd-jg726                                          1/1     Running     0          106m
observability          fluentd-log-retention-29850977-cdbrh                   0/1     Completed   0          12m
observability          kube-state-metrics-757668c8cd-pzslc                    1/1     Running     0          106m
observability          node-exporter-rjwpj                                    1/1     Running     0          106m
observability          prometheus-744757757d-tjq4r                            1/1     Running     0          106m
trafficops             demo-v1-79c45b95f4-trpkh                               1/1     Running     0          107m
trafficops             demo-v2-5cbb4bdbc7-b84mw                               1/1     Running     0          107m
trafficops             trafficops-controller-6d99494c76-pjqxg                 1/1     Running     0          55m

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.8Gi       229Mi       4.1Mi       2.1Gi       2.0Gi
Swap:             0B          0B          0B

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.4G   52G  10% /

$ systemctl --failed --no-pager
  UNIT LOAD ACTIVE SUB DESCRIPTION

0 loaded units listed.

$ kubectl logs -n trafficops deployment/trafficops-controller --since=15m --tail=50

OOM_MATCHES=0
```
