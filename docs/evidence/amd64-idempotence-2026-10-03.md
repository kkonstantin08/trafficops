# TrafficOps AMD64 idempotence — 3 октября 2026

## Environment

Проверка выполнена агентом через SSH на той же VM Ubuntu 24.04.4 LTS, amd64/x86_64, kernel 6.8.0-100-generic, 4 CPU, MemTotal 4015132 KiB, swap 0B. Предыдущие доказательства: [clean bootstrap](amd64-clean-bootstrap-2026-10-03.md), [clean deploy + verify](amd64-clean-deploy-verify-2026-10-03.md), [controller fix и passing full scenario](amd64-scenario-fix-2026-10-03.md). Адреса VM и credentials исключены.

## Tested revision

Exact functional VM SHA `0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f`, detached HEAD, working tree clean до и после всех команд. Remote documentation-only commit `02275362f48c5b04fb8776bc2529eee3d9b38aa0` на VM **не применялся**: fetch/checkout/pull/reset на VM не выполнялись. Локальная documentation branch fix/amd64-bootstrap синхронизирована с этим remote SHA, затем добавлен только данный файл.

## Pre-state

Capture 2026-10-03T19:54:25.312207Z: node vm-928254 Ready, UID `dccf69fa-f8c5-480a-adfa-f1baf3dcab10`, creationTimestamp `2026-10-03T18:34:10Z`. Все 17 long-running pods Running/Ready, restarts=0; штатный Fluentd retention Job Completed. demo-route UID `4614997b-c719-4778-8997-8cd62eed47f0`, created 18:43:18Z; weights v1=100/v2=0. APP_FORCE_ERRORS=false. Release rolled-back, reconcile_required=false, traffic stopped после предыдущего cleanup.

Controller journal: 32 operations. Read-only SQLite connection mode=ro выбирал только operation IDs и state keys release/traffic; sessions, CSRF и Secret data не читались. До запуска сохранён полный набор старых IDs для последующего subset comparison, а не только count. Password file ~/.config/trafficops/admin-password сравнивался внутренним fingerprint на VM; значение осталось в private file mode 0600 и не выводилось/не экспортировалось в evidence. В отчёте публикуется только boolean результата сравнения.

Все три PV и три PVC Bound. Их UID/creationTimestamp сохранены ниже. Pre resources: RAM 3.8Gi total/1.7Gi used/2.1Gi available, swap 0B; disk 58G/5.2G used/52G available.

## Second bootstrap

Команда выполнена один раз, 2026-10-03T19:54:40Z → 19:54:54Z:

```bash
date -Is
set -o pipefail
make bootstrap 2>&1 | tee ~/trafficops-idempotence-bootstrap.log
bootstrap_exit=${PIPESTATUS[0]}
echo "SECOND_BOOTSTRAP_EXIT=$bootstrap_exit"
date -Is
```

**SECOND_BOOTSTRAP_EXIT=0.** Existing managed cluster распознан по admin.conf/bootstrap.env и pinned kubeadm version. Ветка kubeadm init не выполнялась; reset не вызывался. Повторный bootstrap подтвердил существующую API, единственный node, Ready и Available CoreDNS. Log: «Flannel already exists; leaving its current state unchanged.»

Штатный script обновил apt metadata, подтвердил уже установленные pinned пакеты (0 upgraded/newly installed/removed), повторно установил тот же Helm и выполнил предусмотренный systemctl restart containerd. Это повторное применение настройки runtime, а не пересоздание cluster. После bootstrap capture 19:54:59Z: node UID и creationTimestamp совпадают с pre; все старые pod UID совпадают, restart 0, Ready. Storage, пароль, journal и release/traffic state сохранены. Транскрипт приведён ниже.

## Second deploy

Только после успешного bootstrap, один запуск 2026-10-03T19:55:15Z → 19:55:37Z:

```bash
date -Is
set -o pipefail
make deploy 2>&1 | tee ~/trafficops-idempotence-deploy.log
deploy_exit=${PIPESTATUS[0]}
echo "SECOND_DEPLOY_EXIT=$deploy_exit"
date -Is
```

**SECOND_DEPLOY_EXIT=0**, built-in verify **PASS**. Gateway HTTP 200/v1, marker `verify-1f3901cb958a41f8bd97612cfc663e15` найден Fluentd, все пять jobs up со свежими samples, panel/controller HTTP 200. Script сообщил «HTTPRoute demo-route already exists; preserving its current traffic weights.» Route остался 100/0, UID/creationTimestamp прежние.

Cached image build/import, Helm eg revision 3 и декларативные apply/rollout checks выполнены штатно. Deployment controller unchanged; controller pod **не заменился**. Все 17 долгоживущих pod UID и restart counts сохранились. После Helm upgrade кратковременно присутствовал новый штатный certgen Job; в final snapshot его уже нет. Он не считается потерей cluster identity/persistence. PV configured/PVC unchanged не означает recreate: проверены реальные UID.

## Persistence

До → after-bootstrap → after-deploy → post выполнено сравнение:

- **controller password unchanged: true**; fingerprint/пароль не публикуются.
- Node UID/creationTimestamp unchanged: true.
- demo-route UID/creationTimestamp unchanged: true; weights 100/0 unchanged.
- Controller, Prometheus и Fluentd PV/PVC UID/creationTimestamp/Bound unchanged: true.
- Все 32 прежних operation IDs сохранились; current count 32. В том числе прежняя automatic rollback operation `20e9da327365446098fafca73159c590` присутствует после deploy.
- Полные безопасные release/traffic state objects before/after совпадают; rolled_back_at, run_id и traffic counts сохранились, reconcile_required=false.

Это доказательство сохранности существующего state, а не только наличия новых ресурсов. Secret data или password hash в Git не добавлялись. UID storage приведены в таблице ниже, безопасные comparison records — в конце.

## Independent verify

После проверки preservation отдельный запуск 2026-10-03T19:56:03Z → 19:56:10Z:

```bash
date -Is
set -o pipefail
make verify 2>&1 | tee ~/trafficops-idempotence-verify.log
verify_exit=${PIPESTATUS[0]}
echo "SECOND_VERIFY_EXIT=$verify_exit"
date -Is
```

**SECOND_VERIFY_EXIT=0.** Новый Gateway HTTP 200/v1 marker `verify-ee038ab8979b4a88a8d84f4c2ffdc97f` найден в Fluentd destination /logs: event access, version v1, path /demo/region/east, status 200, cri_time 2026-10-03T19:56:04.513079043Z. Panel/controller health HTTP 200/200. GatewayClass Accepted, Gateway Accepted/Programmed, HTTPRoute Accepted/ResolvedRefs — True с актуальными observedGeneration.

Кроме встроенной проверки получены read-only Prometheus query и фактическая Fluentd matching record. Все пять jobs up=1: trafficops-demo-v1, trafficops-demo-v2, envoy-proxy, node-exporter, kube-state-metrics. Capture 1791057433.2935903; timestamp(up) samples 1791057425.846…1791057431.723, age 1.57…7.45s (<30s). v1 HTTP 200 counter 2728 со свежим source timestamp 1791057431.723. Полные safe query records приведены ниже.

## Post-state

Capture 2026-10-03T19:56:41.099381Z и последующий runtime snapshot: node Ready; все 17 long-running pods Running/Ready, restart 0; retention Job Completed. Нет текущих CrashLoopBackOff/ImagePullBackOff/Pending/NotReady. Node и pod identity не изменились; route 100/0, APP_FORCE_ERRORS=false в ConfigMap и mounted file внутри demo-v2. Release rolled-back, reconcile_required=false; traffic stopped. Последний независимый Gateway probe HTTP 200/v1.

RAM 3.8Gi total, около 1.8Gi used, 2.0–2.1Gi available; swap 0B. Disk 58G, 5.4G used,52G available (10%). Failed systemd units 0; read-only kernel journal за последние 20 минут: OOM matches 0. Controller logs за 20 минут пусты, ошибок runtime не выявлено. Рост disk used 5.2→5.4G не сопровождается потерей storage state. Apt сообщил 200 not upgraded; пакетные обновления вне документированного bootstrap не выполнялись.

## Manual fixes

None.

Только документированные make bootstrap → make deploy → make verify. Ручных patches, package fixes, containerd edits, reset/recreate/delete cluster не было. Диагностический script в /tmp только читает Kubernetes/SQLite и сохраняет private comparison markers; не вызывает mutations. make verify-scenario **не запускался**.

## Result

**PASS.** Повторный bootstrap exit 0, cluster identity preserved; повторный deploy exit 0 и built-in verify PASS; пароль, все PV/PVC, прежний journal и release/traffic state сохранены; route 100/0 сохранён; independent verify exit 0; workloads healthy; manual fixes None. Проверено на существующем final 100/0 state; сохранение произвольных активных canary weights этим запуском отдельно не испытывалось.

## Scope

- Security negative tests ещё не выполнены.
- Ручная UI-проверка ещё не выполнена.
- Acceptance/README/passport пока не обновлялись.
- main ещё не merge; remote main остаётся `20e5d247b4b044cec80f1a3c3f03abd940c3574c`.
- Functional code changes: none.
- VM остаётся на functional SHA 0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f; documentation commit на неё не применяется.

## Captured preservation records

| Resource | UID before = after | Creation timestamp before = after |
| --- | --- | --- |
| pv//trafficops-controller-data | `a509154e-ee98-4164-b071-0a89e61eb879` | 2026-10-03T18:43:43Z |
| pv//trafficops-fluentd-logs | `b5c2026e-2b3b-4139-b8ab-f9334edc0311` | 2026-10-03T18:43:30Z |
| pv//trafficops-prometheus | `f634e10f-3277-43d9-82ee-703e287cfd06` | 2026-10-03T18:43:30Z |
| pvc/observability/fluentd-logs | `ca2b17fe-6dff-460a-a21b-000949b728a2` | 2026-10-03T18:43:30Z |
| pvc/observability/prometheus-data | `994fb3f7-a9e0-458a-bdb9-b0e7883ac832` | 2026-10-03T18:43:30Z |
| pvc/trafficops/trafficops-controller-data | `fac856d5-ac9d-4324-9d2e-8338d1729a57` | 2026-10-03T18:43:43Z |

Safe state before/after (одинаковый):

```json
{
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
}
```

### after-bootstrap

```json
{
  "capture_time": 1791057299.4913254,
  "sha": "0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f",
  "git_status": "",
  "node": {
    "name": "vm-928254",
    "uid": "dccf69fa-f8c5-480a-adfa-f1baf3dcab10",
    "creationTimestamp": "2026-10-03T18:34:10Z",
    "arch": "amd64",
    "ready": "True"
  },
  "route": {
    "name": "demo-route",
    "uid": "4614997b-c719-4778-8997-8cd62eed47f0",
    "creationTimestamp": "2026-10-03T18:43:18Z"
  },
  "weights": {
    "demo-v1": 100,
    "demo-v2": 0
  },
  "errors": "false",
  "preservation": {
    "node_uid_unchanged": true,
    "node_creation_unchanged": true,
    "route_uid_unchanged": true,
    "weights_unchanged": true,
    "controller_password_unchanged": true,
    "storage_identities_unchanged": true,
    "all_prior_journal_ids_preserved": true,
    "prior_journal_count": 32,
    "current_journal_count": 32,
    "release_state_unchanged": true,
    "traffic_state_unchanged": true,
    "prior_automatic_rollback_id_preserved": true
  },
  "gatewayclass_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:18Z",
      "message": "Valid GatewayClass",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    }
  ],
  "gateway_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "The Gateway has been scheduled by Envoy Gateway",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    },
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "Address assigned to the Gateway, 1/1 envoy replicas available",
      "observedGeneration": 1,
      "reason": "Programmed",
      "status": "True",
      "type": "Programmed"
    }
  ],
  "httproute_status": [
    {
      "conditions": [
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Route is accepted",
          "observedGeneration": 8,
          "reason": "Accepted",
          "status": "True",
          "type": "Accepted"
        },
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Resolved all the Object references for the Route",
          "observedGeneration": 8,
          "reason": "ResolvedRefs",
          "status": "True",
          "type": "ResolvedRefs"
        }
      ],
      "controllerName": "gateway.envoyproxy.io/gatewayclass-controller",
      "parentRef": {
        "group": "gateway.networking.k8s.io",
        "kind": "Gateway",
        "name": "trafficops"
      }
    }
  ]
}
```

### after-deploy

```json
{
  "capture_time": 1791057348.767938,
  "sha": "0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f",
  "git_status": "",
  "node": {
    "name": "vm-928254",
    "uid": "dccf69fa-f8c5-480a-adfa-f1baf3dcab10",
    "creationTimestamp": "2026-10-03T18:34:10Z",
    "arch": "amd64",
    "ready": "True"
  },
  "route": {
    "name": "demo-route",
    "uid": "4614997b-c719-4778-8997-8cd62eed47f0",
    "creationTimestamp": "2026-10-03T18:43:18Z"
  },
  "weights": {
    "demo-v1": 100,
    "demo-v2": 0
  },
  "errors": "false",
  "preservation": {
    "node_uid_unchanged": true,
    "node_creation_unchanged": true,
    "route_uid_unchanged": true,
    "weights_unchanged": true,
    "controller_password_unchanged": true,
    "storage_identities_unchanged": true,
    "all_prior_journal_ids_preserved": true,
    "prior_journal_count": 32,
    "current_journal_count": 32,
    "release_state_unchanged": true,
    "traffic_state_unchanged": true,
    "prior_automatic_rollback_id_preserved": true
  },
  "gatewayclass_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:18Z",
      "message": "Valid GatewayClass",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    }
  ],
  "gateway_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "The Gateway has been scheduled by Envoy Gateway",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    },
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "Address assigned to the Gateway, 1/1 envoy replicas available",
      "observedGeneration": 1,
      "reason": "Programmed",
      "status": "True",
      "type": "Programmed"
    }
  ],
  "httproute_status": [
    {
      "conditions": [
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Route is accepted",
          "observedGeneration": 8,
          "reason": "Accepted",
          "status": "True",
          "type": "Accepted"
        },
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Resolved all the Object references for the Route",
          "observedGeneration": 8,
          "reason": "ResolvedRefs",
          "status": "True",
          "type": "ResolvedRefs"
        }
      ],
      "controllerName": "gateway.envoyproxy.io/gatewayclass-controller",
      "parentRef": {
        "group": "gateway.networking.k8s.io",
        "kind": "Gateway",
        "name": "trafficops"
      }
    }
  ]
}
```

### post

```json
{
  "capture_time": 1791057401.0993814,
  "sha": "0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f",
  "git_status": "",
  "node": {
    "name": "vm-928254",
    "uid": "dccf69fa-f8c5-480a-adfa-f1baf3dcab10",
    "creationTimestamp": "2026-10-03T18:34:10Z",
    "arch": "amd64",
    "ready": "True"
  },
  "route": {
    "name": "demo-route",
    "uid": "4614997b-c719-4778-8997-8cd62eed47f0",
    "creationTimestamp": "2026-10-03T18:43:18Z"
  },
  "weights": {
    "demo-v1": 100,
    "demo-v2": 0
  },
  "errors": "false",
  "preservation": {
    "node_uid_unchanged": true,
    "node_creation_unchanged": true,
    "route_uid_unchanged": true,
    "weights_unchanged": true,
    "controller_password_unchanged": true,
    "storage_identities_unchanged": true,
    "all_prior_journal_ids_preserved": true,
    "prior_journal_count": 32,
    "current_journal_count": 32,
    "release_state_unchanged": true,
    "traffic_state_unchanged": true,
    "prior_automatic_rollback_id_preserved": true
  },
  "gatewayclass_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:18Z",
      "message": "Valid GatewayClass",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    }
  ],
  "gateway_status": [
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "The Gateway has been scheduled by Envoy Gateway",
      "observedGeneration": 1,
      "reason": "Accepted",
      "status": "True",
      "type": "Accepted"
    },
    {
      "lastTransitionTime": "2026-10-03T18:43:44Z",
      "message": "Address assigned to the Gateway, 1/1 envoy replicas available",
      "observedGeneration": 1,
      "reason": "Programmed",
      "status": "True",
      "type": "Programmed"
    }
  ],
  "httproute_status": [
    {
      "conditions": [
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Route is accepted",
          "observedGeneration": 8,
          "reason": "Accepted",
          "status": "True",
          "type": "Accepted"
        },
        {
          "lastTransitionTime": "2026-10-03T19:43:45Z",
          "message": "Resolved all the Object references for the Route",
          "observedGeneration": 8,
          "reason": "ResolvedRefs",
          "status": "True",
          "type": "ResolvedRefs"
        }
      ],
      "controllerName": "gateway.envoyproxy.io/gatewayclass-controller",
      "parentRef": {
        "group": "gateway.networking.k8s.io",
        "kind": "Gateway",
        "name": "trafficops"
      }
    }
  ]
}
```

## Observability records

```json
{
  "prometheus": [
    {
      "query": "up",
      "capture_time": 1791057433.2920134,
      "status": "success",
      "samples": [
        {
          "job": "trafficops-demo-v2",
          "value": [
            1791057433.291,
            "1"
          ]
        },
        {
          "job": "envoy-proxy",
          "value": [
            1791057433.291,
            "1"
          ]
        },
        {
          "job": "kube-state-metrics",
          "value": [
            1791057433.291,
            "1"
          ]
        },
        {
          "job": "node-exporter",
          "value": [
            1791057433.291,
            "1"
          ]
        },
        {
          "job": "trafficops-demo-v1",
          "value": [
            1791057433.291,
            "1"
          ]
        }
      ]
    },
    {
      "query": "timestamp(up)",
      "capture_time": 1791057433.2935903,
      "status": "success",
      "samples": [
        {
          "job": "trafficops-demo-v2",
          "value": [
            1791057433.293,
            "1791057425.846"
          ]
        },
        {
          "job": "envoy-proxy",
          "value": [
            1791057433.293,
            "1791057427.587"
          ]
        },
        {
          "job": "kube-state-metrics",
          "value": [
            1791057433.293,
            "1791057428.932"
          ]
        },
        {
          "job": "node-exporter",
          "value": [
            1791057433.293,
            "1791057428.681"
          ]
        },
        {
          "job": "trafficops-demo-v1",
          "value": [
            1791057433.293,
            "1791057431.723"
          ]
        }
      ]
    },
    {
      "query": "sum(trafficops_http_requests_total{version=\"v1\",status=\"200\"})",
      "capture_time": 1791057433.2950659,
      "status": "success",
      "samples": [
        {
          "job": null,
          "value": [
            1791057433.294,
            "2728"
          ]
        }
      ]
    },
    {
      "query": "max(timestamp(trafficops_http_requests_total{version=\"v1\",status=\"200\"}))",
      "capture_time": 1791057433.2966146,
      "status": "success",
      "samples": [
        {
          "job": null,
          "value": [
            1791057433.296,
            "1791057431.723"
          ]
        }
      ]
    }
  ],
  "fluentd_matching_record": "{\"cri_time\":\"2026-10-03T19:56:04.513079043Z\",\"stream\":\"stdout\",\"logtag\":\"F\",\"event\":\"access\",\"service\":\"trafficops-demo\",\"version\":\"v1\",\"path\":\"/demo/region/east\",\"status\":200,\"duration_seconds\":0.000256,\"request_id\":\"verify-ee038ab8979b4a88a8d84f4c2ffdc97f\",\"run_id\":\"stage1\"}\n"
}
```

## bootstrap transcript

```text
sudo ./scripts/bootstrap.sh
Hit:1 https://download.docker.com/linux/ubuntu noble InRelease
Hit:3 http://security.ubuntu.com/ubuntu noble-security InRelease
Hit:2 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  InRelease
Hit:4 http://archive.ubuntu.com/ubuntu noble InRelease
Hit:5 http://archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:6 http://archive.ubuntu.com/ubuntu noble-backports InRelease
Reading package lists...
Reading package lists...
Building dependency tree...
Reading state information...
ca-certificates is already the newest version (20260601~24.04.1).
ca-certificates set to manually installed.
curl is already the newest version (8.5.0-2ubuntu10.15).
gpg is already the newest version (2.4.4-2ubuntu17.6).
gpg set to manually installed.
apt-transport-https is already the newest version (2.8.3).
python3 is already the newest version (3.12.3-0ubuntu2.1).
0 upgraded, 0 newly installed, 0 to remove and 202 not upgraded.
Hit:1 https://download.docker.com/linux/ubuntu noble InRelease
Hit:2 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  InRelease
Hit:3 http://archive.ubuntu.com/ubuntu noble InRelease
Hit:4 http://security.ubuntu.com/ubuntu noble-security InRelease
Hit:5 http://archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:6 http://archive.ubuntu.com/ubuntu noble-backports InRelease
Reading package lists...
Reading package lists...
Building dependency tree...
Reading state information...
containerd.io is already the newest version (2.3.6-1~ubuntu.24.04~noble).
docker-ce is already the newest version (5:29.8.1-1~ubuntu.24.04~noble).
docker-ce-cli is already the newest version (5:29.8.1-1~ubuntu.24.04~noble).
docker-buildx-plugin is already the newest version (0.37.1-1~ubuntu.24.04~noble).
kubelet is already the newest version (1.36.5-1.1).
kubeadm is already the newest version (1.36.5-1.1).
kubectl is already the newest version (1.36.5-1.1).
0 upgraded, 0 newly installed, 0 to remove and 200 not upgraded.
containerd.io was already set on hold.
docker-ce was already set on hold.
docker-ce-cli was already set on hold.
docker-buildx-plugin was already set on hold.
kubelet was already set on hold.
kubeadm was already set on hold.
kubectl was already set on hold.
Synchronizing state of docker.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable docker
Flannel already exists; leaving its current state unchanged.
node/vm-928254 condition met
deployment.apps/coredns condition met
Bootstrap ready: Ubuntu 24.04, amd64, Kubernetes 1.36.5, containerd 2.3.6-1~ubuntu.24.04~noble, Flannel 0.28.9, Helm 3.22.0.
SECOND_BOOTSTRAP_EXIT=0
```

## deploy transcript

```text
./scripts/deploy.sh
Building trafficops-demo:0.1.0 from the repository Dockerfile...
#0 building with "default" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 485B done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#2 DONE 0.4s

#3 [internal] load .dockerignore
#3 transferring context: 205B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 487B done
#4 DONE 0.0s

#5 [1/7] FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#5 resolve docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c 0.0s done
#5 DONE 0.0s

#6 [2/7] WORKDIR /app
#6 CACHED

#7 [3/7] COPY requirements.lock /app/requirements.lock
#7 CACHED

#8 [5/7] COPY demo/app.py /app/demo/app.py
#8 CACHED

#9 [6/7] COPY controller /app/controller
#9 CACHED

#10 [4/7] RUN pip install --no-cache-dir --requirement /app/requirements.lock
#10 CACHED

#11 [7/7] COPY web /app/web
#11 CACHED

#12 exporting to image
#12 exporting layers done
#12 exporting manifest sha256:8597144374a3ddb22b20ba3b5424b752c41fb7c0e38fe5b96714ab69187bd94f done
#12 exporting config sha256:a8ade8e446a40e1fbb2e7d24968e8d36c9a9bfeb3dbdd836c5b08028d566c6f5 done
#12 exporting attestation manifest sha256:698637d73e31217fb0b451fe2f02094c243d2797b08e20a4747f4ed6cde93aed done
#12 exporting manifest list sha256:6b1c93969c05926529bab309a378c625dd1f3b45b7d8a703e48f23796d2bd561 done
#12 naming to docker.io/library/trafficops-demo:0.1.0 done
#12 unpacking to docker.io/library/trafficops-demo:0.1.0 done
#12 DONE 0.1s
docker.io/library/trafficops demo:0.1.0 	saved
application/vnd.oci.image.index.v1+json sha256:6b1c93969c05926529bab309a378c625dd1f3b45b7d8a703e48f23796d2bd561
Importing	elapsed: 2.1 s	total:   0.0 B	(0.0 B/s)
namespace/trafficops configured
namespace/trafficops configured
deployment.apps/demo-v1 unchanged
service/demo-v1 unchanged
deployment.apps/demo-v2 unchanged
service/demo-v2 unchanged
deployment.apps/demo-v1 annotated
deployment "demo-v1" successfully rolled out
deployment.apps/demo-v2 annotated
deployment "demo-v2" successfully rolled out
Pulled: docker.io/envoyproxy/gateway-helm:v1.9.1
Digest: sha256:91bae9aedb91ab34731e987afe01a3ccf454393015abeca705eea8ee15553e86
Release "eg" has been upgraded. Happy Helming!
NAME: eg
LAST DEPLOYED: Sat Oct  3 19:55:20 2026
NAMESPACE: envoy-gateway-system
STATUS: deployed
REVISION: 3
TEST SUITE: None
NOTES:
**************************************************************************
*** PLEASE BE PATIENT: Envoy Gateway may take a few minutes to install ***
**************************************************************************

Envoy Gateway is an open source project for managing Envoy Proxy as a standalone or Kubernetes-based application gateway.

Thank you for installing Envoy Gateway! 🎉

Your release is named: eg. 🎉

Your release is in namespace: envoy-gateway-system. 🎉

To learn more about the release, try:

  $ helm status eg -n envoy-gateway-system
  $ helm get all eg -n envoy-gateway-system

To have a quickstart of Envoy Gateway, please refer to https://gateway.envoyproxy.io/latest/tasks/quickstart.

To get more details, please visit https://gateway.envoyproxy.io and https://github.com/envoyproxy/gateway.
deployment.apps/envoy-gateway condition met
envoyproxy.gateway.envoyproxy.io/trafficops-proxy unchanged
gatewayclass.gateway.networking.k8s.io/trafficops unchanged
gateway.gateway.networking.k8s.io/trafficops unchanged
HTTPRoute demo-route already exists; preserving its current traffic weights.
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
node/vm-928254 not labeled
namespace/observability unchanged
persistentvolume/trafficops-prometheus configured
persistentvolumeclaim/prometheus-data unchanged
persistentvolume/trafficops-fluentd-logs configured
persistentvolumeclaim/fluentd-logs unchanged
serviceaccount/prometheus unchanged
role.rbac.authorization.k8s.io/trafficops-prometheus unchanged
rolebinding.rbac.authorization.k8s.io/trafficops-prometheus unchanged
deployment.apps/prometheus unchanged
service/prometheus unchanged
serviceaccount/kube-state-metrics unchanged
clusterrole.rbac.authorization.k8s.io/trafficops-kube-state-metrics unchanged
clusterrolebinding.rbac.authorization.k8s.io/trafficops-kube-state-metrics unchanged
deployment.apps/kube-state-metrics unchanged
service/kube-state-metrics unchanged
daemonset.apps/node-exporter unchanged
service/node-exporter unchanged
daemonset.apps/fluentd unchanged
cronjob.batch/fluentd-log-retention unchanged
configmap/prometheus-config unchanged
configmap/fluentd-config unchanged
deployment "prometheus" successfully rolled out
deployment "kube-state-metrics" successfully rolled out
daemon set "node-exporter" successfully rolled out
daemon set "fluentd" successfully rolled out
persistentvolume/trafficops-controller-data configured
persistentvolumeclaim/trafficops-controller-data unchanged
serviceaccount/trafficops-controller unchanged
role.rbac.authorization.k8s.io/trafficops-controller unchanged
rolebinding.rbac.authorization.k8s.io/trafficops-controller unchanged
deployment.apps/trafficops-controller unchanged
service/trafficops-controller unchanged
httproute.gateway.networking.k8s.io/trafficops-panel configured
backendtrafficpolicy.gateway.envoyproxy.io/trafficops-panel-idle-timeout unchanged
deployment "trafficops-controller" successfully rolled out
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   81m   v1.36.5   [REDACTED_IP]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       72m
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [REDACTED_IP]   True         72m

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     72m
httproute.gateway.networking.k8s.io/trafficops-panel               71m
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-1f3901cb958a41f8bd97612cfc663e15
Fluentd log verified within 30 seconds: request_id verify-1f3901cb958a41f8bd97612cfc663e15, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200
SECOND_DEPLOY_EXIT=0
```

## verify transcript

```text
./scripts/verify.sh
NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   81m   v1.36.5   [REDACTED_IP]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       72m
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [REDACTED_IP]   True         72m

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     72m
httproute.gateway.networking.k8s.io/trafficops-panel               72m
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-ee038ab8979b4a88a8d84f4c2ffdc97f
Fluentd log verified within 30 seconds: request_id verify-ee038ab8979b4a88a8d84f4c2ffdc97f, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200
SECOND_VERIFY_EXIT=0
```

## Final runtime snapshot

```text
$ kubectl get nodes -o wide
NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   82m   v1.36.5   [REDACTED_IP]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6

$ kubectl get pods -A
NAMESPACE              NAME                                                   READY   STATUS      RESTARTS   AGE
envoy-gateway-system   envoy-gateway-6fbfccc98d-fqglk                         1/1     Running     0          73m
envoy-gateway-system   envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running     0          73m
kube-flannel           kube-flannel-ds-xcfgs                                  1/1     Running     0          82m
kube-system            coredns-589f44dc88-jqt2h                               1/1     Running     0          82m
kube-system            coredns-589f44dc88-kx88r                               1/1     Running     0          82m
kube-system            etcd-vm-928254                                         1/1     Running     0          82m
kube-system            kube-apiserver-vm-928254                               1/1     Running     0          82m
kube-system            kube-controller-manager-vm-928254                      1/1     Running     0          82m
kube-system            kube-proxy-8b98x                                       1/1     Running     0          82m
kube-system            kube-scheduler-vm-928254                               1/1     Running     0          82m
observability          fluentd-jg726                                          1/1     Running     0          72m
observability          fluentd-log-retention-29850917-hc9kz                   0/1     Completed   0          39m
observability          kube-state-metrics-757668c8cd-pzslc                    1/1     Running     0          73m
observability          node-exporter-rjwpj                                    1/1     Running     0          73m
observability          prometheus-744757757d-tjq4r                            1/1     Running     0          73m
trafficops             demo-v1-79c45b95f4-trpkh                               1/1     Running     0          73m
trafficops             demo-v2-5cbb4bdbc7-b84mw                               1/1     Running     0          73m
trafficops             trafficops-controller-6d99494c76-pjqxg                 1/1     Running     0          22m

$ kubectl get httproute demo-route -n trafficops -o yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"gateway.networking.k8s.io/v1","kind":"HTTPRoute","metadata":{"annotations":{},"name":"demo-route","namespace":"trafficops"},"spec":{"parentRefs":[{"name":"trafficops"}],"rules":[{"backendRefs":[{"name":"demo-v1","port":8080,"weight":100},{"name":"demo-v2","port":8080,"weight":0}],"matches":[{"path":{"type":"PathPrefix","value":"/demo"}}]}]}}
  creationTimestamp: "2026-10-03T18:43:18Z"
  generation: 8
  name: demo-route
  namespace: trafficops
  resourceVersion: "8876"
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
    - lastTransitionTime: "2026-10-03T19:43:45Z"
      message: Route is accepted
      observedGeneration: 8
      reason: Accepted
      status: "True"
      type: Accepted
    - lastTransitionTime: "2026-10-03T19:43:45Z"
      message: Resolved all the Object references for the Route
      observedGeneration: 8
      reason: ResolvedRefs
      status: "True"
      type: ResolvedRefs
    controllerName: gateway.envoyproxy.io/gatewayclass-controller
    parentRef:
      group: gateway.networking.k8s.io
      kind: Gateway
      name: trafficops

$ kubectl get configmap demo-v2-config -n trafficops -o yaml
apiVersion: v1
data:
  APP_FORCE_ERRORS: "false"
kind: ConfigMap
metadata:
  creationTimestamp: "2026-10-03T18:42:50Z"
  name: demo-v2-config
  namespace: trafficops
  resourceVersion: "8880"
  uid: 55eef85c-e4aa-4372-948f-37ba8ca68af5

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.8Gi       172Mi       4.1Mi       2.2Gi       2.0Gi
Swap:             0B          0B          0B

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.4G   52G  10% /

$ systemctl --failed --no-pager
  UNIT LOAD ACTIVE SUB DESCRIPTION

0 loaded units listed.

$ kubectl logs -n trafficops deployment/trafficops-controller --since=20m --tail=50

RECENT_OOM_MATCHES=0

MOUNTED_ERRORS=false
```
