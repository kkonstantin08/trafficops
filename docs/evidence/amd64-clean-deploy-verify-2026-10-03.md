# AMD64 clean deploy + verify — 3 октября 2026

## Environment

Та же Ubuntu 24.04.4 LTS AMD64/x86_64 VM, 4 CPU, MemTotal 4015132 KiB, около 4 GB RAM, swap 0B. Исходное состояние и успешный первый bootstrap: [clean-bootstrap evidence](amd64-clean-bootstrap-2026-10-03.md). Этот этап выполнен агентом через SSH; credentials и IP не публикуются.

## Tested revision

- Repository: https://github.com/kkonstantin08/trafficops
- Branch: `fix/amd64-bootstrap`.
- **Exact VM SHA:** `6c611c46862061caba371b27b9df2e062f2753be` — та же ревизия bootstrap.
- Её parent `e24aa05c9618d9bb462515371088b816b566eb1b` содержит согласованную AMD64 implementation revision; 6c611c добавляет только preflight evidence.
- Последующий `f319209e2d1ba3b3b4794af564404e535853825f` добавил только clean-bootstrap evidence. Он не применялся на VM: git pull/fetch/update checkout перед deploy/verify не выполнялись.
- Локальная документация создана поверх f319209; локальный и remote HEAD до создания evidence совпали. Рабочие деревья до проверки чистые.

## Continuity

Подключение к той же назначенной VM и существующему /root/trafficops. В pre-deploy snapshot тот же node vm-928254, Kubernetes v1.36.5 и те же имена всех восьми системных pods, что в bootstrap evidence; все Running/Ready, RESTARTS 0. Node creationTimestamp 2026-10-03T18:34:10Z совпадает с интервалом первого bootstrap; node UID dccf69fa-f8c5-480a-adfa-f1baf3dcab10. До deploy дополнительных runtime действий агент не выполнял. После verify HEAD по-прежнему 6c611c, git status --short пустой.

```text
2026-10-03T18:42:30+00:00
fix/amd64-bootstrap
6c611c46862061caba371b27b9df2e062f2753be
NAME        STATUS   ROLES           AGE     VERSION
vm-928254   Ready    control-plane   8m20s   v1.36.5
NAMESPACE      NAME                                READY   STATUS    RESTARTS   AGE
kube-flannel   kube-flannel-ds-xcfgs               1/1     Running   0          8m12s
kube-system    coredns-589f44dc88-jqt2h            1/1     Running   0          8m11s
kube-system    coredns-589f44dc88-kx88r            1/1     Running   0          8m11s
kube-system    etcd-vm-928254                      1/1     Running   0          8m18s
kube-system    kube-apiserver-vm-928254            1/1     Running   0          8m18s
kube-system    kube-controller-manager-vm-928254   1/1     Running   0          8m18s
kube-system    kube-proxy-8b98x                    1/1     Running   0          8m12s
kube-system    kube-scheduler-vm-928254            1/1     Running   0          8m18s
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.0Gi       896Mi       2.4Mi       2.2Gi       2.8Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  3.6G   54G   7% /
=== CLUSTER ID ===
name=vm-928254 uid=dccf69fa-f8c5-480a-adfa-f1baf3dcab10 created=2026-10-03T18:34:10Z
```

## Deploy

Exact command:

```bash
date -Is
set -o pipefail
make deploy 2>&1 | tee ~/trafficops-clean-deploy.log
deploy_exit=${PIPESTATUS[0]}
echo "DEPLOY_EXIT=$deploy_exit"
date -Is
```

Start: 2026-10-03T18:42:37+00:00 (21:42:37 MSK).
End: 2026-10-03T18:43:56+00:00 (21:43:56 MSK).
**DEPLOY_EXIT=0.**

Docker build из закреплённого Python base image с requirements.lock успешен; image trafficops-demo:0.1.0 сохранён и импортирован в containerd namespace k8s.io. Затем script создал demo-v1/v2, установил Helm release eg (Envoy Gateway v1.9.1, revision 1), дождался Gateway conditions, создал Prometheus/Fluentd/node-exporter/kube-state-metrics с AMD64 pins и локальными PV, создал controller и panel HTTPRoute и дождался rollout.

Script сам выполнил rollout restart demo-v1/v2 на первичном deploy и config-hash patch Prometheus/Fluentd; эти действия — часть deploy, а не ручные fixes. Generated admin password сохранён script вне repository; ни пароль, ни Secret contents не читались и не публикуются.

## Built-in verify

**PASS** внутри make deploy. Gateway HTTP 200/version v1, request_id `verify-f90406cb97dc4dedbcdb3f9fbb97a8e0`, run_id stage1; соответствующая Fluentd запись найдена в пределах 30 секунд. Verify подтвердил свежие up для пяти jobs, HTTP 200 counter v1, panel/controller HTTP 200/200. Полный transcript ниже.

## Independent verify

Exact command:

```bash
date -Is
set -o pipefail
make verify 2>&1 | tee ~/trafficops-clean-verify.log
verify_exit=${PIPESTATUS[0]}
echo "VERIFY_EXIT=$verify_exit"
date -Is
```

Start: 2026-10-03T18:44:18+00:00.
End: 2026-10-03T18:44:24+00:00.
**VERIFY_EXIT=0.**

### Application / Gateway

Фактический запрос verify: HTTP GET через Envoy Gateway NodePort 30080, Host trafficops.local, path `/demo/region/east?request_id=verify-ca16d08673a245aa99776de85184a963&run_id=stage1`. Это запрос через Gateway, а не прямой Service. HTTP 200, version v1; verify также проверил JSON service=trafficops-demo, region=east, exact request_id и run_id=stage1, соответствие текущим route weights.

Conditions получены отдельным kubectl get -o json; generation/observedGeneration=1:

- GatewayClass trafficops: Accepted=True.
- Gateway trafficops: Accepted=True, Programmed=True.
- HTTPRoute demo-route: Accepted=True, ResolvedRefs=True.
- HTTPRoute trafficops-panel: Accepted=True, ResolvedRefs=True.

```json
{"kind": "gatewayclass", "name": "trafficops", "generation": 1, "conditions": [{"lastTransitionTime": "2026-10-03T18:43:18Z", "message": "Valid GatewayClass", "observedGeneration": 1, "reason": "Accepted", "status": "True", "type": "Accepted"}]}
{"kind": "gateway", "name": "trafficops", "generation": 1, "conditions": [{"lastTransitionTime": "2026-10-03T18:43:44Z", "message": "The Gateway has been scheduled by Envoy Gateway", "observedGeneration": 1, "reason": "Accepted", "status": "True", "type": "Accepted"}, {"lastTransitionTime": "2026-10-03T18:43:44Z", "message": "Address assigned to the Gateway, 1/1 envoy replicas available", "observedGeneration": 1, "reason": "Programmed", "status": "True", "type": "Programmed"}]}
{"kind": "httproute", "name": "demo-route", "generation": 1, "conditions": [{"lastTransitionTime": "2026-10-03T18:43:18Z", "message": "Route is accepted", "observedGeneration": 1, "reason": "Accepted", "status": "True", "type": "Accepted"}, {"lastTransitionTime": "2026-10-03T18:43:18Z", "message": "Resolved all the Object references for the Route", "observedGeneration": 1, "reason": "ResolvedRefs", "status": "True", "type": "ResolvedRefs"}]}
{"kind": "httproute", "name": "trafficops-panel", "generation": 1, "conditions": [{"lastTransitionTime": "2026-10-03T18:43:44Z", "message": "Route is accepted", "observedGeneration": 1, "reason": "Accepted", "status": "True", "type": "Accepted"}, {"lastTransitionTime": "2026-10-03T18:43:44Z", "message": "Resolved all the Object references for the Route", "observedGeneration": 1, "reason": "ResolvedRefs", "status": "True", "type": "ResolvedRefs"}]}
NODE_CONDITIONS [{"lastHeartbeatTime": "2026-10-03T18:34:25Z", "lastTransitionTime": "2026-10-03T18:34:25Z", "message": "Flannel is running on this node", "reason": "FlannelIsUp", "status": "False", "type": "NetworkUnavailable"}, {"lastHeartbeatTime": "2026-10-03T18:43:43Z", "lastTransitionTime": "2026-10-03T18:34:09Z", "message": "kubelet has sufficient memory available", "reason": "KubeletHasSufficientMemory", "status": "False", "type": "MemoryPressure"}, {"lastHeartbeatTime": "2026-10-03T18:43:43Z", "lastTransitionTime": "2026-10-03T18:34:09Z", "message": "kubelet has no disk pressure", "reason": "KubeletHasNoDiskPressure", "status": "False", "type": "DiskPressure"}, {"lastHeartbeatTime": "2026-10-03T18:43:43Z", "lastTransitionTime": "2026-10-03T18:34:09Z", "message": "kubelet has sufficient PID available", "reason": "KubeletHasSufficientPID", "status": "False", "type": "PIDPressure"}, {"lastHeartbeatTime": "2026-10-03T18:43:43Z", "lastTransitionTime": "2026-10-03T18:34:23Z", "message": "kubelet is posting ready status", "reason": "KubeletReady", "status": "True", "type": "Ready"}]
PODS 17
```

### Prometheus

Pod prometheus-744757757d-tjq4r Running/Ready, restart 0. Verify использует queries `up`, `timestamp(up)`, `trafficops_http_requests_total{version="v1",status="200"}`, `timestamp(trafficops_http_requests_total{version="v1",status="200"})`. Он требует положительный app counter и sample age от -5 до 30 секунд.

Отдельная read-only проверка через ограниченный по времени kubectl port-forward service/prometheus на loopback повторно получила targets и непустые PromQL results. Все пять targets up, lastError пустой. up=1 для каждого job; sample age 2.420–8.297 секунд; app counter=2, age=2.427 секунды. Instance IP labels исключены, значения сохранены:

```text
PROM_CAPTURE_TIME 1791053124.0836484
TARGETS [{"job": "envoy-proxy", "health": "up", "lastScrape": "2026-10-03T18:45:17.587374158Z", "lastError": ""}, {"job": "kube-state-metrics", "health": "up", "lastScrape": "2026-10-03T18:45:18.932400506Z", "lastError": ""}, {"job": "node-exporter", "health": "up", "lastScrape": "2026-10-03T18:45:18.681904786Z", "lastError": ""}, {"job": "trafficops-demo-v1", "health": "up", "lastScrape": "2026-10-03T18:45:21.72375069Z", "lastError": ""}, {"job": "trafficops-demo-v2", "health": "up", "lastScrape": "2026-10-03T18:45:15.846413752Z", "lastError": ""}]
{"query": "up", "status": "success", "result": [{"labels": {"__name__": "up", "job": "trafficops-demo-v2", "version": "v2"}, "value": [1791053124.138, "1"]}, {"labels": {"__name__": "up", "job": "envoy-proxy"}, "value": [1791053124.138, "1"]}, {"labels": {"__name__": "up", "job": "kube-state-metrics"}, "value": [1791053124.138, "1"]}, {"labels": {"__name__": "up", "job": "node-exporter"}, "value": [1791053124.138, "1"]}, {"labels": {"__name__": "up", "job": "trafficops-demo-v1", "version": "v1"}, "value": [1791053124.138, "1"]}]}
{"query": "timestamp(up)", "status": "success", "result": [{"labels": {"job": "trafficops-demo-v2", "version": "v2"}, "value": [1791053124.142, "1791053115.846"], "sample_age_seconds": 8.297}, {"labels": {"job": "envoy-proxy"}, "value": [1791053124.142, "1791053117.587"], "sample_age_seconds": 6.556}, {"labels": {"job": "kube-state-metrics"}, "value": [1791053124.142, "1791053118.932"], "sample_age_seconds": 5.211}, {"labels": {"job": "node-exporter"}, "value": [1791053124.142, "1791053118.681"], "sample_age_seconds": 5.462}, {"labels": {"job": "trafficops-demo-v1", "version": "v1"}, "value": [1791053124.142, "1791053121.723"], "sample_age_seconds": 2.42}]}
{"query": "trafficops_http_requests_total{version=\"v1\",status=\"200\"}", "status": "success", "result": [{"labels": {"__name__": "trafficops_http_requests_total", "exported_version": "v1", "job": "trafficops-demo-v1", "status": "200", "version": "v1"}, "value": [1791053124.146, "2"]}]}
{"query": "timestamp(trafficops_http_requests_total{version=\"v1\",status=\"200\"})", "status": "success", "result": [{"labels": {"exported_version": "v1", "job": "trafficops-demo-v1", "status": "200", "version": "v1"}, "value": [1791053124.149, "1791053121.723"], "sample_age_seconds": 2.427}]}
```

### Fluentd

Pod fluentd-jg726 Running/Ready, restart 0. Destination: /logs/trafficops.*.log в Fluentd pod, PV на VM /var/lib/trafficops/fluentd/logs. Независимый marker `verify-ca16d08673a245aa99776de85184a963` найден verify в пределах 30 секунд. Точное время его polling отдельно script не выводит; весь verify занял 6 секунд, включая последующие metrics/health проверки. Повторный read-only grep подтвердил конкретную запись:

```json
{"cri_time":"2026-10-03T18:44:19.633672059Z","stream":"stdout","logtag":"F","event":"access","service":"trafficops-demo","version":"v1","path":"/demo/region/east","status":200,"duration_seconds":0.000224,"request_id":"verify-ca16d08673a245aa99776de85184a963","run_id":"stage1"}
```

### Controller / panel

Controller trafficops-controller-54ffbd7dd4-r82d7 Running, 1/1, restart 0. Panel / и controller /healthz через Gateway NodePort: HTTP 200/200. Verify проверил HTML lang=ru, TrafficOps и наличие sections overview/traffic/releases/incidents/diagnostics. Авторизованные управляющие операции этим этапом не проверяются; cookies/session/CSRF и secret contents не извлекались.

## Kubernetes state

Все 17 pods Running и Ready, RESTARTS 0 (Envoy proxy 2/2, остальные 1/1); один node Ready. Текущих CrashLoopBackOff/ImagePullBackOff/ErrImagePull/Pending/NotReady нет. Node MemoryPressure/DiskPressure/PIDPressure/NetworkUnavailable=False. Failed systemd units=0; container lastState пустые, OOMKilled не обнаружен. Исторические startup warnings перечислены ниже — они не скрыты и не означают текущую деградацию.

Полный post-deploy snapshot:

```text
NAMESPACE              NAME                                                   READY   STATUS    RESTARTS   AGE     IP               NODE        NOMINATED NODE   READINESS GATES
envoy-gateway-system   envoy-gateway-6fbfccc98d-fqglk                         1/1     Running   0          55s     [redacted-ip]       vm-928254   <none>           <none>
envoy-gateway-system   envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running   0          51s     [redacted-ip]      vm-928254   <none>           <none>
kube-flannel           kube-flannel-ds-xcfgs                                  1/1     Running   0          9m51s   [redacted-ip]   vm-928254   <none>           <none>
kube-system            coredns-589f44dc88-jqt2h                               1/1     Running   0          9m50s   [redacted-ip]       vm-928254   <none>           <none>
kube-system            coredns-589f44dc88-kx88r                               1/1     Running   0          9m50s   [redacted-ip]       vm-928254   <none>           <none>
kube-system            etcd-vm-928254                                         1/1     Running   0          9m57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system            kube-apiserver-vm-928254                               1/1     Running   0          9m57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system            kube-controller-manager-vm-928254                      1/1     Running   0          9m57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system            kube-proxy-8b98x                                       1/1     Running   0          9m51s   [redacted-ip]   vm-928254   <none>           <none>
kube-system            kube-scheduler-vm-928254                               1/1     Running   0          9m57s   [redacted-ip]   vm-928254   <none>           <none>
observability          fluentd-jg726                                          1/1     Running   0          27s     [redacted-ip]      vm-928254   <none>           <none>
observability          kube-state-metrics-757668c8cd-pzslc                    1/1     Running   0          39s     [redacted-ip]      vm-928254   <none>           <none>
observability          node-exporter-rjwpj                                    1/1     Running   0          39s     [redacted-ip]   vm-928254   <none>           <none>
observability          prometheus-744757757d-tjq4r                            1/1     Running   0          38s     [redacted-ip]      vm-928254   <none>           <none>
trafficops             demo-v1-79c45b95f4-trpkh                               1/1     Running   0          78s     [redacted-ip]       vm-928254   <none>           <none>
trafficops             demo-v2-5cbb4bdbc7-b84mw                               1/1     Running   0          72s     [redacted-ip]       vm-928254   <none>           <none>
trafficops             trafficops-controller-54ffbd7dd4-r82d7                 1/1     Running   0          25s     [redacted-ip]      vm-928254   <none>           <none>
=== TRAFFICOPS ===
NAME                                         READY   STATUS    RESTARTS   AGE
pod/demo-v1-79c45b95f4-trpkh                 1/1     Running   0          78s
pod/demo-v2-5cbb4bdbc7-b84mw                 1/1     Running   0          72s
pod/trafficops-controller-54ffbd7dd4-r82d7   1/1     Running   0          25s

NAME                            TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/demo-v1                 ClusterIP   [redacted-ip]   <none>        8080/TCP   78s
service/demo-v2                 ClusterIP   [redacted-ip]   <none>        8080/TCP   78s
service/trafficops-controller   ClusterIP   [redacted-ip]   <none>        8081/TCP   25s

NAME                                    READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/demo-v1                 1/1     1            1           78s
deployment.apps/demo-v2                 1/1     1            1           78s
deployment.apps/trafficops-controller   1/1     1            1           25s

NAME                                               DESIRED   CURRENT   READY   AGE
replicaset.apps/demo-v1-5f5b9f78                   0         0         0       78s
replicaset.apps/demo-v1-79c45b95f4                 1         1         1       78s
replicaset.apps/demo-v2-5cbb4bdbc7                 1         1         1       72s
replicaset.apps/demo-v2-8568855cf                  0         0         0       78s
replicaset.apps/trafficops-controller-54ffbd7dd4   1         1         1       25s
=== OBSERVABILITY ===
NAME                                      READY   STATUS    RESTARTS   AGE
pod/fluentd-jg726                         1/1     Running   0          27s
pod/kube-state-metrics-757668c8cd-pzslc   1/1     Running   0          39s
pod/node-exporter-rjwpj                   1/1     Running   0          39s
pod/prometheus-744757757d-tjq4r           1/1     Running   0          38s

NAME                         TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/kube-state-metrics   ClusterIP   [redacted-ip]       <none>        8080/TCP   39s
service/node-exporter        ClusterIP   [redacted-ip]    <none>        9100/TCP   39s
service/prometheus           ClusterIP   [redacted-ip]   <none>        9090/TCP   39s

NAME                           DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR                           AGE
daemonset.apps/fluentd         1         1         1       1            1           trafficops.io/observability-node=true   39s
daemonset.apps/node-exporter   1         1         1       1            1           kubernetes.io/os=linux                  39s

NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/kube-state-metrics   1/1     1            1           39s
deployment.apps/prometheus           1/1     1            1           39s

NAME                                            DESIRED   CURRENT   READY   AGE
replicaset.apps/kube-state-metrics-757668c8cd   1         1         1       39s
replicaset.apps/prometheus-5d867f4ddc           0         0         0       39s
replicaset.apps/prometheus-744757757d           1         1         1       38s

NAME                                  SCHEDULE     TIMEZONE   SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/fluentd-log-retention   17 * * * *   Etc/UTC    False     0        <none>          39s
=== ENVOY ===
NAME                                                       READY   STATUS    RESTARTS   AGE
pod/envoy-gateway-6fbfccc98d-fqglk                         1/1     Running   0          55s
pod/envoy-trafficops-trafficops-e37760ee-7444fffc4-jx59f   2/2     Running   0          51s

NAME                                           TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)                                            AGE
service/envoy-gateway                          ClusterIP   [redacted-ip]   <none>        18000/TCP,18001/TCP,18002/TCP,19001/TCP,9443/TCP   55s
service/envoy-trafficops-trafficops-e37760ee   NodePort    [redacted-ip]     <none>        80:30080/TCP                                       51s

NAME                                                   READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/envoy-gateway                          1/1     1            1           55s
deployment.apps/envoy-trafficops-trafficops-e37760ee   1/1     1            1           51s

NAME                                                             DESIRED   CURRENT   READY   AGE
replicaset.apps/envoy-gateway-6fbfccc98d                         1         1         1       55s
replicaset.apps/envoy-trafficops-trafficops-e37760ee-7444fffc4   1         1         1       51s
=== GATEWAY API ===
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       52s
NAMESPACE    NAME         CLASS        ADDRESS          PROGRAMMED   AGE
trafficops   trafficops   trafficops   [redacted-ip]   True         52s
NAMESPACE    NAME               HOSTNAMES   AGE
trafficops   demo-route                     52s
trafficops   trafficops-panel               26s
=== RESOURCE SNAPSHOT ===
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.7Gi       156Mi       4.1Mi       2.3Gi       2.1Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.2G   52G   9% /
```

## Resources

После deploy + независимого verify: RAM total 3.8Gi, used 1.7Gi, available 2.1Gi; swap 0B. Disk 58G, used 5.2G, available 52G (9%). Kernel journal за интервал начиная 18:42:30 UTC не содержит out of memory/oom-kill/killed process по выполненному фильтру; node MemoryPressure=False. Metrics-server не устанавливался; kubectl top не требовался. Это краткий snapshot, не нагрузочный soak.

Ниже фактические ресурсы, process snapshot, systemd и warning events:

```text
{"cri_time":"2026-10-03T18:44:19.633672059Z","stream":"stdout","logtag":"F","event":"access","service":"trafficops-demo","version":"v1","path":"/demo/region/east","status":200,"duration_seconds":0.000224,"request_id":"verify-ca16d08673a245aa99776de85184a963","run_id":"stage1"}
=== RESOURCES AFTER DEPLOY ===
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.7Gi       199Mi       4.1Mi       2.3Gi       2.1Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  5.2G   52G   9% /
=== PROCESS SNAPSHOT ===
    PID COMMAND         %CPU %MEM   RSS
   9835 kube-apiserver   6.1 14.5 582560
   9819 kube-controller  1.4  3.0 120980
  14457 envoy-gateway    0.5  2.8 115120
   8619 dockerd          0.4  2.7 111764
   9958 kubelet          2.3  2.4 99804
  15677 prometheus       0.9  2.4 99184
   9192 containerd       4.2  2.0 83808
   9821 etcd             2.3  2.0 83632
  14718 envoy-gateway    0.1  2.0 82540
  14691 envoy            0.4  1.6 67536
   9836 kube-scheduler   0.7  1.5 61696
  10732 coredns          0.1  1.5 60716
  10860 coredns          0.1  1.4 59632
  16396 python           1.9  1.3 53816
  16223 fluentd          1.2  1.3 53804
  15447 kube-state-metr  0.1  1.3 52292
  10500 flanneld         0.1  1.1 47844
  10144 kube-proxy       0.0  1.1 46532
    392 multipathd       0.0  0.6 27456
=== SERVICES ===
  UNIT LOAD ACTIVE SUB DESCRIPTION

0 loaded units listed.
=== WARNING EVENTS ===
NAMESPACE              LAST SEEN   TYPE      REASON                   OBJECT                                       MESSAGE
default                10m         Warning   InvalidDiskCapacity      node/vm-928254                               invalid capacity 0 on image filesystem
kube-system            10m         Warning   Unhealthy                pod/kube-scheduler-vm-928254                 Readiness probe failed: HTTP probe failed with statuscode: 500
kube-system            10m         Warning   FailedMount              pod/kube-proxy-8b98x                         MountVolume.SetUp failed for volume "kube-api-access-m7gll" : configmap "kube-root-ca.crt" not found
kube-flannel           10m         Warning   FailedMount              pod/kube-flannel-ds-xcfgs                    MountVolume.SetUp failed for volume "kube-api-access-fb5kb" : configmap "kube-root-ca.crt" not found
kube-system            10m         Warning   FailedScheduling         pod/coredns-589f44dc88-jqt2h                 0/1 nodes are available: 1 node(s) had untolerated taint(s). no new claims to deallocate, preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
kube-system            10m         Warning   FailedScheduling         pod/coredns-589f44dc88-kx88r                 0/1 nodes are available: 1 node(s) had untolerated taint(s). no new claims to deallocate, preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
kube-system            10m         Warning   FailedCreatePodSandBox   pod/coredns-589f44dc88-jqt2h                 Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "0e727e459c6ba89d216e1995b5fe9bfddb684a814af5a6112a11528eedd74fed": plugin type="flannel" failed (add): failed to load flannel 'subnet.env' file: open /run/flannel/subnet.env: no such file or directory. Check the flannel pod log for this node.
kube-system            10m         Warning   FailedCreatePodSandBox   pod/coredns-589f44dc88-kx88r                 Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "273f407229e419b28bddfdd6abfdb89ddbcfe76aea4ae75a1a6ba67b6482e32d": plugin type="flannel" failed (add): failed to load flannel 'subnet.env' file: open /run/flannel/subnet.env: no such file or directory. Check the flannel pod log for this node.
kube-system            10m         Warning   Unhealthy                pod/coredns-589f44dc88-jqt2h                 Readiness probe failed: Get "http://[redacted-ip]:8181/ready": dial tcp [redacted-ip]:8181: connect: connection refused
kube-system            10m         Warning   Unhealthy                pod/coredns-589f44dc88-kx88r                 Readiness probe failed: Get "http://[redacted-ip]:8181/ready": dial tcp [redacted-ip]:8181: connect: connection refused
trafficops             2m10s       Warning   Unhealthy                pod/demo-v1-5f5b9f78-7fqkb                   Readiness probe failed: Get "http://[redacted-ip]:8080/healthz": dial tcp [redacted-ip]:8080: connect: connection refused
trafficops             2m10s       Warning   Unhealthy                pod/demo-v1-79c45b95f4-trpkh                 Readiness probe failed: Get "http://[redacted-ip]:8080/healthz": dial tcp [redacted-ip]:8080: connect: connection refused
trafficops             2m10s       Warning   Unhealthy                pod/demo-v2-8568855cf-bfnxg                  Readiness probe failed: Get "http://[redacted-ip]:8080/healthz": dial tcp [redacted-ip]:8080: connect: connection refused
trafficops             2m4s        Warning   Unhealthy                pod/demo-v2-5cbb4bdbc7-b84mw                 Readiness probe failed: Get "http://[redacted-ip]:8080/healthz": dial tcp [redacted-ip]:8080: connect: connection refused
envoy-gateway-system   106s        Warning   Unhealthy                pod/envoy-gateway-6fbfccc98d-fqglk           Readiness probe failed: Get "http://[redacted-ip]:8081/readyz": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
observability          92s         Warning   FailedMount              pod/prometheus-5d867f4ddc-kjrdc              MountVolume.SetUp failed for volume "config" : configmap "prometheus-config" not found
observability          91s         Warning   FailedMount              pod/fluentd-b5694                            MountVolume.SetUp failed for volume "config" : configmap "fluentd-config" not found
observability          90s         Warning   Unhealthy                pod/kube-state-metrics-757668c8cd-pzslc      Readiness probe failed: dial tcp [redacted-ip]:8080: connect: connection refused
observability          85s         Warning   Unhealthy                pod/prometheus-744757757d-tjq4r              Readiness probe failed: Get "http://[redacted-ip]:9090/-/ready": dial tcp [redacted-ip]:9090: connect: connection refused
observability          83s         Warning   Unhealthy                pod/prometheus-5d867f4ddc-kjrdc              Readiness probe failed: Get "http://[redacted-ip]:9090/-/ready": dial tcp [redacted-ip]:9090: connect: connection refused
trafficops             78s         Warning   Unhealthy                pod/trafficops-controller-54ffbd7dd4-r82d7   Readiness probe failed: Get "http://[redacted-ip]:8081/healthz": dial tcp [redacted-ip]:8081: connect: connection refused
=== OOM KERNEL CHECK ===
6c611c46862061caba371b27b9df2e062f2753be
```

## Manual fixes

None.

## Result

**PASS** для первого clean deploy + независимого verify: deploy exit 0, встроенный verify PASS, отдельный verify exit 0, Gateway path работает, реальные Prometheus samples свежие, новый Fluentd marker найден, panel/controller healthy, workloads Ready без перезапусков, ручных runtime fixes не было.

Реальные warnings/замечания:
- pip root-user warning внутри контейнерного Docker build и notice о новой pip; build успешен, обновление pip не выполнялось.
- Startup events первого bootstrap: InvalidDiskCapacity, scheduler readiness 500, kube-root-ca ConfigMap FailedMount, CoreDNS scheduling/CNI subnet.env/readiness failures; к pre-deploy все системные pods были здоровы.
- Startup events deploy: временные connection refused/deadline exceeded readiness probes у demo/Envoy/controller/Prometheus/kube-state-metrics; FailedMount до создания prometheus-config/fluentd-config. После rollout все workloads готовы.
- Первичный deploy сам перезапустил demo-v1/v2; промежуточные старые ReplicaSets остались с 0 replicas.
- Приветствие VM сообщает 210 доступных обновлений (157 security); apt upgrade не запускался.
- Нагрузка canary, восстановление и повторный deploy не проверялись; запас ресурсов под ними не заявляется.

## Scope

- make verify-scenario ещё не выполнялся.
- Canary/manual rollback/automatic rollback этим этапом не подтверждаются.
- Повторный bootstrap/deploy ещё не проверен.
- main не изменён; merge не выполнялся.
- Acceptance matrix, README и passport не менялись.
- Functional code changes: none.
- Raw transcripts сохранены на VM: /root/trafficops-clean-deploy.log и /root/trafficops-clean-verify.log. Ниже полные публичные копии с заменой IP и потенциальных token patterns; пробелы в конце строк нормализованы. Credentials/Secret contents не публикуются.

## Deploy transcript (sanitized)

```text

./scripts/deploy.sh
Building trafficops-demo:0.1.0 from the repository Dockerfile...
#0 building with "default" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 485B done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#2 DONE 0.7s

#3 [internal] load .dockerignore
#3 transferring context: 205B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 90.99kB done
#4 DONE 0.0s

#5 [1/7] FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#5 resolve docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c 0.0s done
#5 sha256:dbeb2af0e7bd53c2dff6896f9bde583874dc48fbb85d8cda0e9040dec5424ca8 249B / 249B 0.1s done
#5 sha256:2e8ff2a71e9573673dd17ca594722bd27eed7eb917debc0fb74ff9eb5d522ad1 3.52MB / 3.52MB 0.2s done
#5 sha256:84a2afebaf4de2e8eb885634a69abd0087b79c947c53fa4f0481235d6dfadc6c 13.63MB / 28.24MB 0.3s
#5 sha256:f9f25941dc135427be9d16894ce71a921adff16e2d43060139ed05c33fcd668e 0B / 13.67MB 0.2s
#5 sha256:84a2afebaf4de2e8eb885634a69abd0087b79c947c53fa4f0481235d6dfadc6c 28.24MB / 28.24MB 0.4s done
#5 sha256:f9f25941dc135427be9d16894ce71a921adff16e2d43060139ed05c33fcd668e 13.67MB / 13.67MB 0.3s done
#5 extracting sha256:84a2afebaf4de2e8eb885634a69abd0087b79c947c53fa4f0481235d6dfadc6c
#5 extracting sha256:84a2afebaf4de2e8eb885634a69abd0087b79c947c53fa4f0481235d6dfadc6c 0.9s done
#5 DONE 1.4s

#5 [1/7] FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#5 extracting sha256:2e8ff2a71e9573673dd17ca594722bd27eed7eb917debc0fb74ff9eb5d522ad1 0.1s done
#5 DONE 1.5s

#5 [1/7] FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#5 extracting sha256:f9f25941dc135427be9d16894ce71a921adff16e2d43060139ed05c33fcd668e
#5 extracting sha256:f9f25941dc135427be9d16894ce71a921adff16e2d43060139ed05c33fcd668e 0.5s done
#5 DONE 2.0s

#5 [1/7] FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
#5 extracting sha256:dbeb2af0e7bd53c2dff6896f9bde583874dc48fbb85d8cda0e9040dec5424ca8 done
#5 DONE 2.0s

#6 [2/7] WORKDIR /app
#6 DONE 0.2s

#7 [3/7] COPY requirements.lock /app/requirements.lock
#7 DONE 0.0s

#8 [4/7] RUN pip install --no-cache-dir --requirement /app/requirements.lock
#8 1.807 Collecting annotated-doc==0.0.5 (from -r /app/requirements.lock (line 2))
#8 1.866   Downloading annotated_doc-0.0.5-py3-none-any.whl.metadata (6.5 kB)
#8 1.875 Collecting annotated-types==0.8.0 (from -r /app/requirements.lock (line 3))
#8 1.878   Downloading annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
#8 1.895 Collecting anyio==4.14.2 (from -r /app/requirements.lock (line 4))
#8 1.898   Downloading anyio-4.14.2-py3-none-any.whl.metadata (4.6 kB)
#8 1.916 Collecting certifi==2026.6.17 (from -r /app/requirements.lock (line 5))
#8 1.919   Downloading certifi-2026.6.17-py3-none-any.whl.metadata (2.5 kB)
#8 1.936 Collecting click==8.5.0 (from -r /app/requirements.lock (line 6))
#8 1.938   Downloading click-8.5.0-py3-none-any.whl.metadata (2.6 kB)
#8 2.000 Collecting fastapi==0.141.1 (from -r /app/requirements.lock (line 7))
#8 2.004   Downloading fastapi-0.141.1-py3-none-any.whl.metadata (27 kB)
#8 2.021 Collecting h11==0.16.0 (from -r /app/requirements.lock (line 8))
#8 2.024   Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
#8 2.039 Collecting httpcore==1.0.9 (from -r /app/requirements.lock (line 9))
#8 2.042   Downloading httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
#8 2.061 Collecting httpx==0.28.1 (from -r /app/requirements.lock (line 10))
#8 2.064   Downloading httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
#8 2.077 Collecting idna==3.18 (from -r /app/requirements.lock (line 11))
#8 2.079   Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
#8 2.213 Collecting pydantic==2.13.4 (from -r /app/requirements.lock (line 12))
#8 2.216   Downloading pydantic-2.13.4-py3-none-any.whl.metadata (109 kB)
#8 2.976 Collecting pydantic_core==2.46.4 (from -r /app/requirements.lock (line 13))
#8 2.979   Downloading pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
#8 3.008 Collecting starlette==1.7.0 (from -r /app/requirements.lock (line 14))
#8 3.011   Downloading starlette-1.7.0-py3-none-any.whl.metadata (6.6 kB)
#8 3.020 Collecting typing-inspection==0.4.2 (from -r /app/requirements.lock (line 15))
#8 3.023   Downloading typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
#8 3.037 Collecting typing_extensions==4.16.0 (from -r /app/requirements.lock (line 16))
#8 3.040   Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
#8 3.069 Collecting uvicorn==0.54.0 (from -r /app/requirements.lock (line 17))
#8 3.072   Downloading uvicorn-0.54.0-py3-none-any.whl.metadata (6.6 kB)
#8 3.160 Downloading annotated_doc-0.0.5-py3-none-any.whl (5.3 kB)
#8 3.163 Downloading annotated_types-0.8.0-py3-none-any.whl (13 kB)
#8 3.166 Downloading anyio-4.14.2-py3-none-any.whl (125 kB)
#8 3.169 Downloading certifi-2026.6.17-py3-none-any.whl (133 kB)
#8 3.172 Downloading click-8.5.0-py3-none-any.whl (125 kB)
#8 3.174 Downloading fastapi-0.141.1-py3-none-any.whl (131 kB)
#8 3.177 Downloading h11-0.16.0-py3-none-any.whl (37 kB)
#8 3.181 Downloading httpcore-1.0.9-py3-none-any.whl (78 kB)
#8 3.183 Downloading httpx-0.28.1-py3-none-any.whl (73 kB)
#8 3.186 Downloading idna-3.18-py3-none-any.whl (65 kB)
#8 3.188 Downloading pydantic-2.13.4-py3-none-any.whl (472 kB)
#8 3.192 Downloading pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
#8 3.199    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 486.9 MB/s eta 0:00:00
#8 3.202 Downloading starlette-1.7.0-py3-none-any.whl (78 kB)
#8 3.205 Downloading typing_inspection-0.4.2-py3-none-any.whl (14 kB)
#8 3.208 Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
#8 3.211 Downloading uvicorn-0.54.0-py3-none-any.whl (87 kB)
#8 3.277 Installing collected packages: typing_extensions, idna, h11, click, certifi, annotated-types, annotated-doc, uvicorn, typing-inspection, pydantic_core, httpcore, anyio, starlette, pydantic, httpx, fastapi
#8 4.515 Successfully installed annotated-doc-0.0.5 annotated-types-0.8.0 anyio-4.14.2 certifi-2026.6.17 click-8.5.0 fastapi-0.141.1 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 idna-3.18 pydantic-2.13.4 pydantic_core-2.46.4 starlette-1.7.0 typing-inspection-0.4.2 typing_extensions-4.16.0 uvicorn-0.54.0
#8 4.515 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
#8 4.646
#8 4.646 [notice] A new release of pip is available: 25.0.1 -> 26.2.1
#8 4.646 [notice] To update, run: pip install --upgrade pip
#8 DONE 4.8s

#9 [5/7] COPY demo/app.py /app/demo/app.py
#9 DONE 0.0s

#10 [6/7] COPY controller /app/controller
#10 DONE 0.0s

#11 [7/7] COPY web /app/web
#11 DONE 0.0s

#12 exporting to image
#12 exporting layers
#12 exporting layers 0.9s done
#12 exporting manifest sha256:8597144374a3ddb22b20ba3b5424b752c41fb7c0e38fe5b96714ab69187bd94f done
#12 exporting config sha256:a8ade8e446a40e1fbb2e7d24968e8d36c9a9bfeb3dbdd836c5b08028d566c6f5 done
#12 exporting attestation manifest sha256:db6cbda3a52dc81f096061e007de1c0585b4c5b553b4300fd8c6291e4b197ea1 done
#12 exporting manifest list sha256:8844994658f8cc063594915fe0779d745fd7626ed0297886ce9eccae9c0f3a3e done
#12 naming to docker.io/library/trafficops-demo:0.1.0 done
#12 unpacking to docker.io/library/trafficops-demo:0.1.0
#12 unpacking to docker.io/library/trafficops-demo:0.1.0 0.3s done
#12 DONE 1.2s
docker.io/library/trafficops demo:0.1.0 	saved
application/vnd.oci.image.index.v1+json sha256:8844994658f8cc063594915fe0779d745fd7626ed0297886ce9eccae9c0f3a3e
Importing	elapsed: 3.2 s	total:   0.0 B	(0.0 B/s)
namespace/trafficops created
configmap/demo-v2-config created
namespace/trafficops configured
deployment.apps/demo-v1 created
service/demo-v1 created
deployment.apps/demo-v2 created
service/demo-v2 created
deployment.apps/demo-v1 restarted
deployment.apps/demo-v1 annotated
Waiting for deployment "demo-v1" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "demo-v1" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "demo-v1" rollout to finish: 1 old replicas are pending termination...
deployment "demo-v1" successfully rolled out
deployment.apps/demo-v2 restarted
deployment.apps/demo-v2 annotated
Waiting for deployment "demo-v2" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "demo-v2" rollout to finish: 1 old replicas are pending termination...
deployment "demo-v2" successfully rolled out
Release "eg" does not exist. Installing it now.
Pulled: docker.io/envoyproxy/gateway-helm:v1.9.1
Digest: sha256:91bae9aedb91ab34731e987afe01a3ccf454393015abeca705eea8ee15553e86
NAME: eg
LAST DEPLOYED: Sat Oct  3 18:43:06 2026
NAMESPACE: envoy-gateway-system
STATUS: deployed
REVISION: 1
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
envoyproxy.gateway.envoyproxy.io/trafficops-proxy created
gatewayclass.gateway.networking.k8s.io/trafficops created
gateway.gateway.networking.k8s.io/trafficops created
httproute.gateway.networking.k8s.io/demo-route created
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
node/vm-928254 labeled
namespace/observability created
persistentvolume/trafficops-prometheus created
persistentvolumeclaim/prometheus-data created
persistentvolume/trafficops-fluentd-logs created
persistentvolumeclaim/fluentd-logs created
serviceaccount/prometheus created
role.rbac.authorization.k8s.io/trafficops-prometheus created
rolebinding.rbac.authorization.k8s.io/trafficops-prometheus created
deployment.apps/prometheus created
service/prometheus created
serviceaccount/kube-state-metrics created
clusterrole.rbac.authorization.k8s.io/trafficops-kube-state-metrics created
clusterrolebinding.rbac.authorization.k8s.io/trafficops-kube-state-metrics created
deployment.apps/kube-state-metrics created
service/kube-state-metrics created
daemonset.apps/node-exporter created
service/node-exporter created
daemonset.apps/fluentd created
cronjob.batch/fluentd-log-retention created
configmap/prometheus-config created
deployment.apps/prometheus patched
configmap/fluentd-config created
daemonset.apps/fluentd patched
Waiting for deployment "prometheus" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "prometheus" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "prometheus" rollout to finish: 1 old replicas are pending termination...
deployment "prometheus" successfully rolled out
deployment "kube-state-metrics" successfully rolled out
daemon set "node-exporter" successfully rolled out
Waiting for daemon set "fluentd" rollout to finish: 0 out of 1 new pods have been updated...
Waiting for daemon set "fluentd" rollout to finish: 0 out of 1 new pods have been updated...
Waiting for daemon set "fluentd" rollout to finish: 0 of 1 updated pods are available...
daemon set "fluentd" successfully rolled out
secret/trafficops-controller created
Controller password saved outside the repository: /root/.config/trafficops/admin-password
persistentvolume/trafficops-controller-data created
persistentvolumeclaim/trafficops-controller-data created
serviceaccount/trafficops-controller created
role.rbac.authorization.k8s.io/trafficops-controller created
rolebinding.rbac.authorization.k8s.io/trafficops-controller created
deployment.apps/trafficops-controller created
service/trafficops-controller created
httproute.gateway.networking.k8s.io/trafficops-panel created
Waiting for deployment "trafficops-controller" rollout to finish: 0 of 1 updated replicas are available...
deployment "trafficops-controller" successfully rolled out
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
NAME        STATUS   ROLES           AGE     VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   9m40s   v1.36.5   [redacted-ip]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       32s
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [redacted-ip]   True         32s

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     32s
httproute.gateway.networking.k8s.io/trafficops-panel               6s
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-f90406cb97dc4dedbcdb3f9fbb97a8e0
Fluentd log verified within 30 seconds: request_id verify-f90406cb97dc4dedbcdb3f9fbb97a8e0, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200

```

## Independent verify transcript (sanitized)

```text
./scripts/verify.sh
NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   10m   v1.36.5   [redacted-ip]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAME         CONTROLLER                                      ACCEPTED   AGE
trafficops   gateway.envoyproxy.io/gatewayclass-controller   True       60s
NAME                                           CLASS        ADDRESS          PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/trafficops   trafficops   [redacted-ip]   True         60s

NAME                                                   HOSTNAMES   AGE
httproute.gateway.networking.k8s.io/demo-route                     60s
httproute.gateway.networking.k8s.io/trafficops-panel               34s
gatewayclass.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
gateway.gateway.networking.k8s.io/trafficops condition met
httproute.gateway.networking.k8s.io/demo-route condition met
httproute.gateway.networking.k8s.io/demo-route condition met
Gateway response verified: HTTP 200, version v1, request_id verify-ca16d08673a245aa99776de85184a963
Fluentd log verified within 30 seconds: request_id verify-ca16d08673a245aa99776de85184a963, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
httproute.gateway.networking.k8s.io/trafficops-panel condition met
httproute.gateway.networking.k8s.io/trafficops-panel condition met
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200

```
