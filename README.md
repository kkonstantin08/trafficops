# TrafficOps

TrafficOps — локальная лаборатория эксплуатации HTTP-сервиса. Этапы 1–3 описывают один Kubernetes-узел, две версии приложения, Envoy Gateway, Prometheus, Fluentd и ограниченный управляющий API со светлой панелью. Gateway отправляет `/demo` на `v1`; панель позволяет запускать конечную серию трафика, canary-релиз, инциденты и подтверждённый откат.

## Компоненты

| Компонент | Версия | Установка |
| --- | --- | --- |
| Ubuntu | 24.04, ARM64 | Проверяется bootstrap-скриптом; живой запуск ещё не подтверждён |
| Kubernetes / kubeadm / kubelet / kubectl | 1.36.5 (`1.36.5-1.1`) | Официальный репозиторий `pkgs.k8s.io` |
| containerd | 2.3.6 | `containerd.io` из официального репозитория Docker |
| Envoy Gateway | 1.9.1 | Официальный OCI Helm chart |
| Flannel | 0.28.9 | Манифест официального GitHub-релиза |
| Helm | 3.22.0 | Официальный ARM64 архив с закреплённой SHA-256 |
| Docker Engine / Buildx | 29.8.1 / 0.37.1 | Сборка локального образа; Kubernetes использует containerd |
| Demo app | Python 3.12.12 | Образ из корневого `Dockerfile`; базовый multi-arch образ закреплён по digest |
| Prometheus | 3.14.0 | ARM64 digest в `deploy/versions.env`; scrape каждые 10 секунд, TSDB 24 часа / 512 MB |
| Fluentd | 1.19.3 Debian | ARM64 digest в `deploy/versions.env`; встроенный `regexp` parser для строк CRI |
| node-exporter | 1.12.1 | ARM64 digest; host metrics с read-only mount `/proc`, `/sys` и `/` |
| kube-state-metrics | 2.20.0 | ARM64 digest; ограничен ресурсами pods, deployments и nodes |
| Controller API | FastAPI 0.141.1 / Uvicorn 0.54.0 | Ограниченные действия в namespace `trafficops`, состояние операций в SQLite |

Официальные release/tag сведения: [Prometheus](https://github.com/prometheus/prometheus/releases/tag/v3.14.0), [Fluentd image](https://github.com/fluent/fluentd-docker-image/releases/tag/v1.19.3-2.2), [node-exporter](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1), [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics/releases/tag/v2.20.0). Фактически проверенные ARM64 digests закреплены в [versions.env](deploy/versions.env). Используются штатные [Fluentd regexp parser](https://docs.fluentd.org/parser/regexp) и [JSON parser filter](https://docs.fluentd.org/filter/parser); список ресурсов kube-state-metrics ограничен поддерживаемым флагом `--resources`. Envoy proxy target использует owning-Gateway labels и порт `19001` согласно [руководству Envoy Gateway 1.9](https://gateway.envoyproxy.io/v1.9/tasks/observability/proxy-metric/).

Kubernetes 1.36 и Envoy Gateway 1.9 совместимы по [официальной матрице Envoy Gateway](https://gateway.envoyproxy.io/news/releases/matrix/). Образы Envoy Gateway, Envoy proxy и Flannel проверены на наличие `linux/arm64` 30 сентября 2026. Демо-приложение использует стандартную библиотеку Python; controller API использует закреплённые FastAPI/Uvicorn зависимости из [requirements.lock](requirements.lock). Точный базовый образ Python закреплён по digest в [Dockerfile](Dockerfile).

## Требования к VM

- Ubuntu Server 24.04, архитектура `arm64`.
- Preflight bootstrap требует не менее 2 vCPU и 3 GiB общей гостевой памяти. Этого условия недостаточно, чтобы заявить достаточность ресурсов для всех компонентов: расход на полной установке ещё не измерен.
- Доступ в интернет к официальным репозиториям Ubuntu, Kubernetes, Docker, GitHub, OCI registry Docker Hub и `get.helm.sh`.
- Свободные сетевые порты для Kubernetes API, kubelet, Flannel VXLAN и Envoy NodePort `30080`.
- Пользователь с `sudo`.

Обычный `make bootstrap` принимает только Ubuntu 24.04 ARM64. Для согласованной проверки на текущей Ubuntu 22.04.5 ARM64 VM предусмотрен отдельный `make bootstrap-dev`: он использует пакеты официального Docker репозитория для Jammy и не засчитывается как приёмка на Ubuntu 24.04. Не передавайте Noble-пакеты в Jammy.

Bootstrap отключает swap для kubelet, устанавливает точные версии зависимостей, создаёт одноузловой кластер `kubeadm` и ставит Flannel. Скрипт откажется менять существующий Kubernetes-кластер, если он не создан TrafficOps. Он не запускает `kubeadm reset` и не удаляет ресурсы. Параметры containerd не перезаписываются: при уже существующем несовместимом `/etc/containerd/config.toml` скрипт остановится и оставит файл без изменений. В dev режиме для Python 3.10 ставится Ubuntu пакет `python3-tomli` для проверки TOML; Python в образе приложения остаётся 3.12.12.

## Установка и проверка внутри терминала Ubuntu VM

Команды выполняются **в терминале Ubuntu VM**, не через SSH и не на Mac:

```bash
sudo apt-get update
sudo apt-get install -y git make curl
git clone https://github.com/kkonstantin08/trafficops.git
cd trafficops
make bootstrap
make deploy
make verify
```

Для текущей Ubuntu 22.04 VM вместо `make bootstrap` используйте `make bootstrap-dev`. Этот явный dev режим не подтверждает требование Ubuntu 24.04.

Команды `make deploy` и `make verify` используют отдельный kubeconfig `~/.kube/trafficops.conf` и не меняют существующий `~/.kube/config`. При первом deploy создаётся пароль панели; он хранится в `~/.config/trafficops/admin-password`, а его PBKDF2 hash попадает в Kubernetes Secret. Файлы создаются вне Git с режимом `0600`. Сохраните пароль, он не выводится в терминал. При уже существующем Secret deploy не меняет учётные данные.

`make deploy` собирает образ на ARM64 VM, импортирует его в namespace `k8s.io` containerd, ждёт готовности Deployments и Envoy Gateway, создаёт начальные Gateway-ресурсы и проверяет маршрут. Повторный запуск безопасен: он сохраняет уже существующие веса HTTPRoute и не перезапускает приложение без изменения исходников. Bootstrap также безопасен для повторного запуска на кластере, созданном этим проектом.

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

Внешний адрес VM зависит от сетевого режима UTM. Его можно посмотреть внутри VM через `hostname -I`; если режим сети позволяет доступ с Mac, тот же запрос можно выполнить с Mac, заменив адрес. NodePort открыт на TCP `30080`; маршруты Gateway не ограничены hostname и доступны по адресу узла без настройки hosts-файла.

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

В браузере VM откройте `http://127.0.0.1:9090`. `make verify` проверяет фактические значения `up` для всех пяти scrape jobs, свежесть их исходных samples через `timestamp(up)`, и свежий счётчик контрольного HTTP-запроса. Время выполнения PromQL-запроса само по себе свежестью sample не считается.

Fluentd tail-читает только `/var/log/pods/trafficops_demo-v1-*` и `/var/log/pods/trafficops_demo-v2-*`; вход смонтирован read-only. Штатный regexp parser выделяет время CRI, поток, признак `F/P` и JSON приложения, который затем разбирается встроенным JSON parser. Неподходящие формату CRI строки сохраняются как unmatched records, а неполный/невалидный JSON отправляется в отдельный `trafficops-parse-errors` файл Fluentd. Файловый буфер ограничен 64 MB для обычных записей и 16 MB для ошибок разбора, интервал flush — 2 секунды, переполнение оставляет ошибку в журнале Fluentd.

Чтобы `make verify` мог найти контрольный access-маркер максимум за 30 секунд, выходные файлы разбиты по 10-секундным окнам; это отклонение от почасовой ротации из плана. Fluentd держит незаписанные chunks в отдельном файловом буфере, а ограниченный CronJob каждый час удаляет закрытые файлы старше 24 часов только из `/logs`, не затрагивая текущие chunks. Размер `capacity: 2Gi` у local PV задаёт Kubernetes для привязки, но сам по себе не является дисковой квотой для host path; расход диска в VM надо измерить при live-приёмке.

`make verify` отправляет запрос через Gateway, немедленно начинает bounded-поиск JSON access-записи в Fluentd PV и затем проверяет Prometheus. Для ручного просмотра логов используйте:

```bash
kubectl exec -n observability daemonset/fluentd -- \
  /bin/sh -c 'grep -hF "verify-" /logs/trafficops.*.log | tail -n 5'
```

## Панель и безопасные операции

После `make deploy` откройте `http://<IP-узла>:30080` в браузере. Панель содержит обзор, трафик, релизы, инциденты и диагностику. Для просмотра логов, журнала операций и фактических метрик вход не нужен; управляющие действия доступны после входа паролем, созданным при deploy. Cookie имеет флаги HttpOnly и SameSite=Strict. Запросы управления проверяют точный Origin и CSRF-токен. Поскольку локальный адрес использует HTTP, cookie не Secure; не публикуйте NodePort в недоверенной сети.

Controller работает только с фиксированными объектами namespace `trafficops`: HTTPRoute `demo-route`, Deployments `demo-v1`/`demo-v2`, ConfigMap `demo-v2-config` и pod-ами demo-приложения. Клиент передаёт только ограниченные параметры: разрешённый путь, скорость 1–20 запросов/с и длительность 1–180 секунд (не более 3600 запросов), либо процент веса v2. Произвольные URL, команды, имена ресурсов и манифесты API не принимает. RBAC разрешает лишь чтение/patch фиксированных ресурсов и выборочное удаление demo pod. SQLite хранится на local PV; директория логов Fluentd подключена только для чтения.

Начните тестовый поток из раздела «Трафик». Canary начинает с 90/10 и оценивает v2 только по свежим исходным samples Prometheus: окно 60 секунд, минимум 30 запросов, доля 5xx строго больше 5%, две проверки подряд с интервалом 10 секунд. Перед оценкой должно пройти полное окно с начала текущего canary. Неизвестная/устаревшая метрика блокирует расширение и завершение релиза; ручной rollback на v1 не зависит от Prometheus. Откат считается успешным только после подтверждения текущего поколения HTTPRoute и ответа `v1` через Gateway. Неудачный откат отображается как `rollback-failed`/`reconcile-required` и не повторяется автоматически.

В разделе «Инциденты» можно включить HTTP 500 для v2 через обновляемый ConfigMap или удалить один выбранный сервером demo pod. Приложение v2 читает конфигурационный файл с периодической проверкой; изменение не обещает мгновенного применения. После удаления pod контроллер ждёт replacement и проверяет HTTP через Gateway. Если подтверждение маршрута или откат не удалось, сначала используйте ручной откат; требуемые фактические веса, причина и операция остаются в журнале. После перезапуска controller незавершённые операции помечаются interrupted, а сохранённые веса сравниваются с маршрутом.

`make verify-scenario` запускает отдельный сквозной сценарий в установленной VM через реальный controller API и Gateway. Команда берёт private InternalIP из `~/.kube/trafficops.conf`, а пароль — из `${XDG_CONFIG_HOME:-~/.config}/trafficops/admin-password`; cookie и CSRF остаются только в памяти, пароль не выводится. Перед изменениями она требует стабильный маршрут v1=100/v2=0 и стандартную canary policy (60 секунд, 30 запросов, 5%, 2 breach checks через 10 секунд); с другой policy команда завершится без изменения ресурсов.

Сценарий выключает ошибки v2, ждёт 130 секунд обновления ConfigMap-проекции, запускает поток 20 запросов/с максимум на 180 секунд, подтверждает свежую здоровую canary-метрику, завершает релиз и проверяет HTTP v2. Затем проверяет ручной откат на HTTP v1, останавливает поток, включает ошибки v2, повторяет ограниченный поток и ждёт автоматический откат с достаточным свежим 5xx sample и записью в журнале. Healthy decision ограничен 135 секундами; ожидание автоматического отката — 290 секундами с учётом проекции, окна и проверок. При любой ошибке `finally` по очереди пытается остановить трафик, отключить v2 ошибки, выполнить ручной откат и выйти из сессии; ошибка очистки выводится отдельно от основной причины. Запускайте команду только при стабильном v1 маршруте и отсутствии другого активного трафика: это демонстрационный сценарий, который меняет ресурсы приложения. CLI и cleanup проверены локально; пользователь предоставил успешный журнал полного сценария на Ubuntu 24.04 ([результаты](docs/evidence/vm-ubuntu24-2026-10-01.md)).

## Границы проверки

Пользователь предоставил [журнал Ubuntu 24.04 ARM64](docs/evidence/vm-ubuntu24-2026-10-01.md): deploy, verify и verify-scenario прошли. Подтверждены HTTP через Gateway, свежие Prometheus samples, доставка контрольного маркера Fluentd, HTTP-доступность панели/API, здоровый релиз v2, ручной и автоматический rollback до v1, очистка и повторное развёртывание. Агент не подключался к VM; результаты записаны по предоставленному журналу. Сборка AMD64/ARM64 подтверждена GitHub Actions. Открыты чистая установка кластера на Ubuntu 24.04, восстановление pod, негативные Origin/CSRF проверки в VM, ручная проверка панели, сохранность старых данных и измерение ресурсов.

## Инструкция и комплект сдачи

Подробный порядок действий в локальной UTM VM: [docs/verification.md](docs/verification.md). [Источник черновика паспорта](docs/passport.md) и [PDF](output/pdf/TrafficOps-passport-draft.pdf) описывают текущую реализацию и открытые проверки. Черновик не является готовым комплектом сдачи: сведения участника и оставшиеся проверки ещё не внесены. Публичный репозиторий: [https://github.com/kkonstantin08/trafficops](https://github.com/kkonstantin08/trafficops).

CI запускает unit/syntax/schema checks и сборку приложения для AMD64/ARM64 без публикации: [.github/workflows/ci.yml](.github/workflows/ci.yml). [Успешный запуск CI](https://github.com/kkonstantin08/trafficops/actions/runs/36775869932) подтвердил 31 тест, 36 схем и сборку AMD64/ARM64; [доказательство](docs/evidence/public-repository-2026-10-01.md). Итоговые независимые результаты: [evidence оркестратора](docs/evidence/orchestrator-local-2026-09-30.md).
