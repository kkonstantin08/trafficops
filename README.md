# TrafficOps

TrafficOps — локальная лаборатория эксплуатации HTTP-сервиса. Этапы 1–3 описывают один Kubernetes-узел, две версии приложения, Envoy Gateway, Prometheus, Fluentd и ограниченный управляющий API со светлой панелью. Gateway отправляет `/demo` на `v1`; панель позволяет запускать конечную серию трафика, canary-релиз, инциденты и подтверждённый откат.

## Компоненты

| Компонент | Версия | Установка |
| --- | --- | --- |
| Ubuntu | 24.04, amd64 / arm64 | Поддерживаются `amd64`/`x86_64` и `arm64`/`aarch64`; Ubuntu 24.04 AMD64 clean-room запуск подтверждён, [ARM64 runtime evidence](docs/evidence/vm-ubuntu24-2026-10-01.md) сохранено отдельно |
| Kubernetes / kubeadm / kubelet / kubectl | 1.36.5 (`1.36.5-1.1`) | Официальный репозиторий `pkgs.k8s.io` |
| containerd | 2.3.6 | `containerd.io` из официального репозитория Docker |
| Envoy Gateway | 1.9.1 | Официальный OCI Helm chart |
| Flannel | 0.28.9 | Манифест официального GitHub-релиза |
| Helm | 3.22.0 | Официальные архивы amd64/arm64 с отдельными закреплёнными SHA-256 |
| Docker Engine / Buildx | 29.8.1 / 0.37.1 | Сборка локального образа; Kubernetes использует containerd |
| Demo app | Python 3.12.12 | Образ из корневого `Dockerfile`; базовый multi-arch образ закреплён по digest |
| Prometheus | 3.14.0 | Отдельные amd64/arm64 digests в `deploy/versions.env`; scrape каждые 10 секунд, TSDB 24 часа / 512 MB |
| Fluentd | 1.19.3 Debian | Отдельные amd64/arm64 digests; встроенный `regexp` parser для строк CRI |
| node-exporter | 1.12.1 | Отдельные amd64/arm64 digests; host metrics с read-only mount `/proc`, `/sys` и `/` |
| kube-state-metrics | 2.20.0 | Отдельные amd64/arm64 digests; ограничен ресурсами pods, deployments и nodes |
| Controller API | FastAPI 0.141.1 / Uvicorn 0.54.0 | Ограниченные действия в namespace `trafficops`, состояние операций в SQLite |

Официальные release/tag сведения: [Prometheus](https://github.com/prometheus/prometheus/releases/tag/v3.14.0), [Fluentd image](https://github.com/fluent/fluentd-docker-image/releases/tag/v1.19.3-2.2), [node-exporter](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1), [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics/releases/tag/v2.20.0). Проверенные platform-specific digests для amd64 и arm64 закреплены в [versions.env](deploy/versions.env). Используются штатные [Fluentd regexp parser](https://docs.fluentd.org/parser/regexp) и [JSON parser filter](https://docs.fluentd.org/filter/parser); список ресурсов kube-state-metrics ограничен поддерживаемым флагом `--resources`. Envoy proxy target использует owning-Gateway labels и порт `19001` согласно [руководству Envoy Gateway 1.9](https://gateway.envoyproxy.io/v1.9/tasks/observability/proxy-metric/).

Kubernetes 1.36 и Envoy Gateway 1.9 совместимы по [официальной матрице Envoy Gateway](https://gateway.envoyproxy.io/news/releases/matrix/). Образы Envoy Gateway, Envoy proxy и Flannel имеют `linux/amd64` и `linux/arm64` descriptors; код выбирает observability digest по архитектуре единственного Kubernetes-узла. Демо-приложение использует стандартную библиотеку Python; controller API использует закреплённые FastAPI/Uvicorn зависимости из [requirements.lock](requirements.lock). Точный базовый образ Python закреплён по digest в [Dockerfile](Dockerfile).

Основные версии пакетов, Helm archive checksums и platform-specific OCI image digests закреплены. Полная hermetic фиксация всех пакетов из APT не заявляется: clean bootstrap также разрешил транзитивные зависимости `docker-ce-rootless-extras`, `docker-compose-plugin`, `kubernetes-cni` и `pigz` из настроенных Ubuntu/Docker repositories; их версии отдельно не pin-ятся в `versions.env` ([clean bootstrap evidence](docs/evidence/amd64-clean-bootstrap-2026-10-03.md)).

## Требования к VM

- Ubuntu Server 24.04; поддерживаемые пары архитектур: Debian `amd64` / kernel `x86_64` и Debian `arm64` / kernel `aarch64`.
- **Минимум, проверяемый bootstrap:** 2 CPU и 3 GiB `MemTotal`. Этот hard guard не гарантирует достаточность ресурсов для любой нагрузки.
- **Конфигурация успешной clean-room AMD64 приёмки:** Ubuntu 24.04.4 LTS, `amd64` / `x86_64`, 4 CPU, `MemTotal=4015132 KiB` (около 3.8 GiB), без swap; корневая файловая система 58 GB. Это снимок одной тестовой VM, а не требуемый минимум.
- Доступ в интернет к официальным репозиториям Ubuntu, Kubernetes, Docker, GitHub, OCI registry Docker Hub и `get.helm.sh`.
- Свободные сетевые порты для Kubernetes API, kubelet, Flannel VXLAN и Envoy NodePort `30080`.
- Пользователь с `sudo`.

`make bootstrap` принимает Ubuntu 24.04 на обеих поддерживаемых архитектурах. Дополнительный `make bootstrap-dev` предназначен только для разработчика на Ubuntu 22.04/Jammy; он использует пакеты Docker для Jammy и не заменяет Ubuntu 24.04 приёмку. Не устанавливайте Noble-пакеты в Jammy.

Bootstrap отключает swap для kubelet, устанавливает основные закреплённые версии, создаёт одноузловой кластер `kubeadm` и ставит Flannel. Он отказывается менять существующий Kubernetes-кластер, если тот не создан TrafficOps; `kubeadm reset` и удаление ресурсов не выполняются. Параметры containerd не перезаписываются: при уже существующем несовместимом `/etc/containerd/config.toml` скрипт остановится и оставит файл без изменений. В dev режиме для Python 3.10 ставится Ubuntu пакет `python3-tomli` для проверки TOML; Python в образе приложения остаётся 3.12.12.

Clean-room bootstrap на новой Ubuntu 24.04.4 AMD64 VM прошёл с `make bootstrap` exit 0. До проверки отсутствовали Docker/containerd, Kubernetes и Helm; единственными вручную запрошенными prerequisites были `git`, `make`, `curl`. После bootstrap единственный узел был `Ready`, Flannel и CoreDNS работали; ручных исправлений не потребовалось. Полные условия и выводы приведены в [AMD64 bootstrap evidence](docs/evidence/amd64-clean-bootstrap-2026-10-03.md).

## Установка и проверка

Выполняйте команды на Ubuntu Server 24.04 — в локальном терминале или через SSH:

```bash
sudo apt-get update
sudo apt-get install -y git make curl
git clone https://github.com/kkonstantin08/trafficops.git
cd trafficops
make bootstrap
make deploy
make verify
```

Проверенная AMD64 implementation lineage перенесена fast-forward в `main`; обычный public clone теперь получает основной воспроизводимый путь. Clean-room runtime evidence относится к functional revision lineage, испытанной до documentation finalization ([post-merge evidence](docs/evidence/main-finalization-2026-10-04.md)).

На чистой Ubuntu 24.04.4 AMD64 `make deploy` завершился с exit 0; встроенный verify и отдельный `make verify` прошли. GatewayClass был `Accepted=True`, Gateway — `Accepted=True/Programmed=True`, HTTPRoutes — `Accepted=True/ResolvedRefs=True`; запрос через Gateway вернул HTTP 200, его access-маркер найден в Fluentd, все пять Prometheus jobs имели свежие `up=1`, health panel/controller вернул HTTP 200. См. [clean deploy/verify evidence](docs/evidence/amd64-clean-deploy-verify-2026-10-03.md).

Для дополнительного developer-only режима на Ubuntu 22.04/Jammy замените `make bootstrap` на `make bootstrap-dev`; остальные команды остаются теми же. Этот режим не является основной приёмочной средой.

Команды `make deploy` и `make verify` используют отдельный kubeconfig `~/.kube/trafficops.conf` и не меняют существующий `~/.kube/config`. При первом deploy создаётся пароль панели; он хранится в `~/.config/trafficops/admin-password`, а его PBKDF2 hash попадает в Kubernetes Secret. Файлы создаются вне Git с режимом `0600`. Сохраните пароль, он не выводится в терминал. При уже существующем Secret deploy не меняет учётные данные.

`make deploy` проверяет совпадение архитектуры хоста и единственного Kubernetes-узла, собирает образ на VM и импортирует его в namespace `k8s.io` containerd. Скрипт ждёт готовности Deployments и Envoy Gateway, создаёт Gateway-ресурсы и проверяет маршрут. Повторные `make bootstrap → make deploy → make verify` прошли на той же AMD64 VM: сохранились UID узла и маршрута, пароль панели, три PV/PVC, журнал операций и состояние release/traffic; verify завершился успешно. Это подтверждено для задокументированной конфигурации, не является тестом произвольной нагрузки ([idempotence evidence](docs/evidence/amd64-idempotence-2026-10-03.md)).

После полного deploy в одном из runtime snapshots было 3.8 GiB RAM total, 1.7–1.8 GiB used и 2.0–2.1 GiB available; на root filesystem 58 GB было занято около 5.4 GB. В проверенном 20-минутном окне OOM matches не обнаружены. Это измерения конкретной VM и коротких окон, а не гарантия capacity или soak/load результат ([idempotence evidence](docs/evidence/amd64-idempotence-2026-10-03.md), [RBAC post-verify snapshot](docs/evidence/amd64-rbac-2026-10-03.md)).

## Проверка HTTP через Gateway

`make verify` подтверждает принятые GatewayClass/Gateway/HTTPRoute, разрешённые ссылки и полный запрос через Envoy NodePort. Ожидается HTTP 200 и тело JSON вида:

```json
{"service":"trafficops-demo","version":"v1","region":"east","request_id":"verify-...","run_id":"stage1"}
```

Чтобы выполнить контрольный запрос вручную внутри VM:

```bash
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
curl --fail-with-body -H 'Host: trafficops.local' \
  "http://${NODE_IP}:30080/demo/region/east?request_id=manual-check-1&run_id=stage1"
```

Для запроса из другой машины используйте routable IP Ubuntu VM и убедитесь, что сеть/firewall пропускает TCP `30080`; адреса и правила зависят от среды. NodePort открыт на TCP `30080`; маршруты Gateway не ограничены hostname и доступны по адресу узла без настройки hosts-файла. Локальная UTM VM — один из вариантов среды, не требование.

## HTTP-приложение

- `GET /healthz` — HTTP 200 для Kubernetes probes.
- `GET /metrics` — Prometheus text format; `/healthz` и `/metrics` не входят в пользовательский счётчик.
- `GET /demo` и `GET /demo/region/east|west` — JSON с версией, регионом и `request_id`/`run_id`.
- Запросы передают маркеры заголовками `X-Request-ID`/`X-Run-ID` либо параметрами `request_id`/`run_id`. Маркер ограничен 64 символами `[A-Za-z0-9._:-]`; отсутствующий маркер генерируется автоматически.
- `APP_FORCE_ERRORS=true` включает демонстрационный HTTP 500 на запросах `/demo`; по умолчанию значение `false`. Базовый манифест не задаёт эту переменную, поэтому повторный deploy сохраняет установленное позже состояние инцидента v2.
- Приложение пишет одну компактную JSON access-запись на запрос в stdout и дополнительную JSON error-запись при HTTP 5xx. Fluentd собирает записи в файловую точку назначения; панель показывает исходный CRI timestamp.

Метрики приложения: `trafficops_http_requests_total{version,status}` и `trafficops_http_request_duration_seconds{version}`. Уникальные request/run-маркеры не используются как labels.

## Метрики и логи

`make deploy` устанавливает Prometheus и Fluentd вместе с приложением. Prometheus доступен внутри кластера как `prometheus.observability.svc:9090`; рабочая конфигурация и все версии находятся в `deploy/`. Локальные тома располагаются в `/var/lib/trafficops/prometheus` и `/var/lib/trafficops/fluentd` на узле Kubernetes.

Prometheus опрашивает `demo-v1`, `demo-v2`, Envoy proxy, node-exporter и kube-state-metrics каждые 10 секунд. Примеры запросов:

```promql
sum by (version, status) (rate(trafficops_http_requests_total[1m]))
sum by (version) (rate(trafficops_http_requests_total{status=~"5.."}[1m]))
node_memory_MemAvailable_bytes
rate(node_cpu_seconds_total[1m])
kube_deployment_status_replicas_available{namespace="trafficops"}
```

Откройте Prometheus внутри VM:

```bash
kubectl port-forward -n observability service/prometheus 9090:9090
```

В браузере VM откройте `http://localhost:9090`. `make verify` проверяет фактические значения `up` для всех пяти scrape jobs, свежесть их исходных samples через `timestamp(up)`, и свежий счётчик контрольного HTTP-запроса. Время выполнения PromQL-запроса само по себе свежестью sample не считается.

Fluentd tail-читает только `/var/log/pods/trafficops_demo-v1-*` и `/var/log/pods/trafficops_demo-v2-*`; вход смонтирован read-only. Штатный regexp parser выделяет время CRI, поток, признак `F/P` и JSON приложения, который затем разбирается встроенным JSON parser. Неподходящие формату CRI строки сохраняются как unmatched records, а неполный/невалидный JSON отправляется в отдельный `trafficops-parse-errors` файл Fluentd. Файловый буфер ограничен 64 MB для обычных записей и 16 MB для ошибок разбора, интервал flush — 2 секунды, переполнение оставляет ошибку в журнале Fluentd.

Чтобы `make verify` мог найти контрольный access-маркер максимум за 30 секунд, выходные файлы разбиты по 10-секундным окнам; это отклонение от почасовой ротации из плана. Fluentd держит незаписанные chunks в отдельном файловом буфере, а ограниченный CronJob каждый час удаляет закрытые файлы старше 24 часов только из `/logs`, не затрагивая текущие chunks. Размер `capacity: 2Gi` у local PV задаёт Kubernetes для привязки, но сам по себе не является дисковой квотой для host path; расход диска в VM надо измерить при live-приёмке.

`make verify` отправляет запрос через Gateway, немедленно начинает bounded-поиск JSON access-записи в Fluentd PV и затем проверяет Prometheus. Для ручного просмотра логов используйте:

```bash
kubectl exec -n observability daemonset/fluentd -- \
  /bin/sh -c 'grep -hF "verify-" /logs/trafficops.*.log | tail -n 5'
```

## Панель и безопасные операции

После `make deploy` панель и controller отвечали HTTP 200 через IP VM. Панель содержит обзор, трафик, релизы, инциденты и диагностику. Для просмотра логов, журнала операций и фактических метрик вход не нужен; управляющие действия доступны после входа паролем, созданным при deploy. Cookie имеет `HttpOnly` и `SameSite=Strict`; live suite также подтвердил эти атрибуты. `Secure=false`, поскольку demo использует HTTP. Запросы управления проверяют точный Origin и CSRF-токен. Не публикуйте NodePort в недоверенной сети. Новую browser visual verification на AMD64 не выполняли.

Controller принимает только заранее определённые операции и ограниченные параметры: разрешённый путь, скорость 1–20 запросов/с и длительность 1–180 секунд (не более 3600 запросов), либо процент веса v2. Произвольные URL, команды, имена ресурсов и манифесты API не принимает. Kubernetes Role ограничивает HTTPRoute `demo-route` правами get/patch по `resourceNames`, Deployments `demo-v1`/`demo-v2` — get по `resourceNames`, ConfigMap `demo-v2-config` — get/patch по `resourceNames`. Для pod recovery ServiceAccount имеет get/list/delete pods без `resourceNames` в namespace `trafficops`. Код контроллера дополнительно выбирает demo pods по label selector, но это не Kubernetes authorization boundary: технически ServiceAccount может удалить любой pod в namespace. Это известное least-privilege ограничение; см. [live RBAC evidence](docs/evidence/amd64-rbac-2026-10-03.md). SQLite хранится на local PV; директория логов Fluentd подключена только для чтения.

Live HTTP security negative suite через Gateway выполнил 25 ограниченных запросов: проверены missing/wrong Origin, неверный и oversized пароль, отсутствие сессии, missing/invalid CSRF, границы path/rate/duration/release weight, logout и replay старой session. Все ожидаемые ответы совпали, операционное состояние не изменилось. Это ограниченный negative test, не penetration test ([security evidence](docs/evidence/amd64-security-negative-2026-10-03.md)).

Начните тестовый поток из раздела «Трафик». Canary начинает с 90/10 и оценивает v2 только по свежим исходным samples Prometheus: окно 60 секунд, минимум 30 запросов, доля 5xx строго больше 5%, две проверки подряд с интервалом 10 секунд. Перед оценкой должно пройти полное окно с начала текущего canary. Неизвестная/устаревшая метрика блокирует расширение и завершение релиза; ручной rollback на v1 не зависит от Prometheus. Откат считается успешным только после подтверждения текущего поколения HTTPRoute и ответа `v1` через Gateway. Неудачный откат отображается как `rollback-failed`/`reconcile-required` и не повторяется автоматически.

В разделе «Инциденты» можно включить HTTP 500 для v2 через обновляемый ConfigMap или удалить один выбранный сервером demo pod. Приложение v2 читает конфигурационный файл с периодической проверкой; изменение не обещает мгновенного применения. После удаления pod контроллер ждёт replacement и проверяет HTTP через Gateway. Если подтверждение маршрута или откат не удалось, сначала используйте ручной откат; требуемые фактические веса, причина и операция остаются в журнале. После перезапуска controller незавершённые операции помечаются interrupted, а сохранённые веса сравниваются с маршрутом.

`make verify-scenario` запускает отдельный сквозной сценарий в установленной VM через реальный controller API и Gateway. Команда берёт private InternalIP из `~/.kube/trafficops.conf`, а пароль — из `${XDG_CONFIG_HOME:-~/.config}/trafficops/admin-password`; cookie и CSRF остаются только в памяти, пароль не выводится. Перед изменениями она требует стабильный маршрут v1=100/v2=0 и стандартную canary policy (60 секунд, 30 запросов, 5%, 2 breach checks через 10 секунд); с другой policy команда завершится без изменения ресурсов.

Сценарий выключает ошибки v2, ждёт до 130 секунд обновления ConfigMap-проекции, запускает поток до 20 запросов/с максимум на 180 секунд, подтверждает свежее здоровое canary-окно и завершает релиз до v2=100. Затем он проверяет HTTP v2 через Gateway, ручной rollback до v1, включает ошибки v2 и повторяет поток. При двух последовательных свежих breach checks выше порога 5% ожидаются automatic rollback, веса v1=100/v2=0, запись причины и подтверждённый HTTP v1 через Gateway. Healthy decision ограничен 135 секундами; ожидание автоматического отката — 290 секундами. `finally` пытается остановить трафик, выключить ошибки, выполнить ручной откат и выйти из сессии; ошибка очистки выводится отдельно. Запускайте без параллельных управляющих действий: это bounded сценарий, который меняет ресурсы приложения.

Один полный AMD64 scenario завершился exit 0 после исправления transient `503 UC` на controller route. Uvicorn keep-alive задан 30 секунд, а Envoy idle timeout для panel route — 15 секунд; evidence называет reuse/idle-close на границе keep-alive наиболее вероятной причиной, а не доказанной единственной причиной. После изменения 85/85 targeted Gateway requests вернули HTTP 200; затем здоровый canary, completion v2, ручной откат, v2 HTTP 5xx и автоматический rollback к v1 прошли, cleanup завершился без ошибки. Подробности: [AMD64 controller fix и scenario evidence](docs/evidence/amd64-scenario-fix-2026-10-03.md), functional fix revision `0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f`.

## Границы проверки

На новой Ubuntu 24.04.4 AMD64 VM агент через SSH выполнил clean bootstrap, deploy, verify и последующий full scenario. Фактические результаты подтверждают:

- clean bootstrap exit 0; node Ready, Flannel/CoreDNS healthy, без ручных fixes ([bootstrap evidence](docs/evidence/amd64-clean-bootstrap-2026-10-03.md));
- GatewayClass/Gateway/HTTPRoutes приняты, запрос через Gateway — HTTP 200, пять Prometheus jobs up со свежими samples, маркер найден Fluentd, controller/panel health — HTTP 200 ([deploy/verify evidence](docs/evidence/amd64-clean-deploy-verify-2026-10-03.md));
- healthy canary и completion до v2, ручной rollback, контролируемые v2 5xx и подтверждённый automatic rollback до v1 ([scenario evidence](docs/evidence/amd64-scenario-fix-2026-10-03.md));
- повторные bootstrap → deploy → verify сохранили cluster/resource identity, пароль, storage и operation/release state; наблюдавшихся OOM за проверенные 20 минут не было ([idempotence evidence](docs/evidence/amd64-idempotence-2026-10-03.md));
- 25 HTTP security negative checks и 34 live RBAC boundary checks прошли без operational side effects ([security evidence](docs/evidence/amd64-security-negative-2026-10-03.md), [RBAC evidence](docs/evidence/amd64-rbac-2026-10-03.md));
- runtime snapshot этой VM: 3.8 GiB total, примерно 1.7–1.8 GiB used и 2.0–2.1 GiB available; root filesystem 58 GB, около 5.4 GB used. Это короткий snapshot, не capacity guarantee или soak/load test.

Ограничения и незавершённые проверки:

- новая AMD64 browser visual verification не выполнялась; HTTP health/API проверялись, но рендер панели глазами не подтверждался;
- security suite — ограниченные negative tests, не полноценный penetration test; длительный soak/load test не выполнялся; TLS в demo не настроен;
- pod delete разрешён ServiceAccount для любого pod в namespace `trafficops`; фильтр demo pods в приложении не является RBAC boundary;
- транзитивные APT dependencies не все зафиксированы отдельными pins;
- финальный submission bundle ещё не подготовлен; паспорт финализирован.

## Инструкция и комплект сдачи

Подробный порядок действий для Ubuntu Server 24.04: [docs/verification.md](docs/verification.md). [Источник паспорта](docs/passport.md) и [Паспорт.pdf](output/pdf/Паспорт.pdf) описывают подтверждённую реализацию и ограничения; [проверка паспорта](docs/evidence/passport-final-2026-10-04.md) завершена. Submission bundle ещё не подготовлен. Публичный репозиторий: [https://github.com/kkonstantin08/trafficops](https://github.com/kkonstantin08/trafficops).

CI запускает unit/syntax/schema checks и сборку приложения для AMD64/ARM64 без публикации: [.github/workflows/ci.yml](.github/workflows/ci.yml). Последний успешный CI перед этим обновлением README/runbook: [run 37154586966](https://github.com/kkonstantin08/trafficops/actions/runs/37154586966), для acceptance commit `53115d172f66c704b812fe4c8129c86e310b7866`. Подробные live результаты находятся в перечисленных выше AMD64 evidence; CI не заменяет runtime acceptance.
