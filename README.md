# TrafficOps

TrafficOps — локальная лаборатория эксплуатации HTTP-сервиса. Этап 1 поднимает один Kubernetes-узел, две версии демонстрационного приложения и Envoy Gateway. Gateway отправляет `/demo` на `v1`; `v2` уже развёрнута и готова к следующим сценариям.

## Состав этапа 1

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

Kubernetes 1.36 и Envoy Gateway 1.9 совместимы по [официальной матрице Envoy Gateway](https://gateway.envoyproxy.io/news/releases/matrix/). Образы Envoy Gateway, Envoy proxy и Flannel проверены на наличие `linux/arm64` 30 сентября 2026. Требуемый lock-файл сообщает, что приложению нужны только стандартные библиотеки Python; точный образ Python закреплён в [Dockerfile](Dockerfile).

## Требования к VM

- Ubuntu Server 24.04, архитектура `arm64`.
- Не менее 2 vCPU и 3 GiB доступной гостевой памяти для preflight этапа 1. Это не оценка достаточности ресурсов для будущих Prometheus, Fluentd и панели.
- Доступ в интернет к официальным репозиториям Ubuntu, Kubernetes, Docker, GitHub, OCI registry Docker Hub и `get.helm.sh`.
- Свободные сетевые порты для Kubernetes API, kubelet, Flannel VXLAN и Envoy NodePort `30080`.
- Пользователь с `sudo`.

Bootstrap отключает swap для kubelet, устанавливает точные версии зависимостей, создаёт одноузловой кластер `kubeadm` и ставит Flannel. Скрипт откажется менять существующий Kubernetes-кластер, если он не создан TrafficOps. Он не запускает `kubeadm reset` и не удаляет ресурсы. Параметры containerd не перезаписываются: при уже существующем несовместимом `/etc/containerd/config.toml` скрипт остановится и оставит файл без изменений.

## Установка и проверка внутри терминала Ubuntu VM

Команды выполняются **в терминале Ubuntu VM**, не через SSH и не на Mac:

```bash
sudo apt-get update
sudo apt-get install -y git make curl
git clone <URL публичного репозитория>
cd "МТС Hakaton"
make bootstrap
make deploy
make verify
```

Замените `<URL публичного репозитория>` адресом опубликованного репозитория. Команды `make deploy` и `make verify` используют отдельный kubeconfig `~/.kube/trafficops.conf` и не меняют существующий `~/.kube/config`.

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

Внешний адрес VM зависит от сетевого режима UTM. Его можно посмотреть внутри VM через `hostname -I`; если режим сети позволяет доступ с Mac, тот же запрос можно выполнить с Mac, заменив адрес. На этапе 1 NodePort открыт на TCP `30080`; приложение также доступно только через Gateway на маршруте `/demo`.

## HTTP-приложение

- `GET /healthz` — HTTP 200 для Kubernetes probes.
- `GET /metrics` — Prometheus text format; `/healthz` и `/metrics` не входят в пользовательский счётчик.
- `GET /demo` и `GET /demo/region/east|west` — JSON с версией, регионом и `request_id`/`run_id`.
- Запросы передают маркеры заголовками `X-Request-ID`/`X-Run-ID` либо параметрами `request_id`/`run_id`. Маркер ограничен 64 символами `[A-Za-z0-9._:-]`; отсутствующий маркер генерируется автоматически.
- `APP_FORCE_ERRORS=true` включает демонстрационный HTTP 500 на запросах `/demo`. В Kubernetes для этапа 1 это выключено.
- Приложение пишет одну компактную JSON access-запись на запрос в stdout и дополнительную JSON error-запись при HTTP 5xx. На этапе 2 Fluentd начнёт передавать эти записи в точку назначения.

Метрики приложения: `trafficops_http_requests_total{version,status}` и `trafficops_http_request_duration_seconds{version}`. Уникальные request/run-маркеры не используются как labels.

## Границы проверки

Компоненты и скрипты записаны. Unit-тесты приложения можно выполнить локально; сборка контейнерного образа и запуск на Ubuntu VM требуют доступного Docker daemon и стенда, которых в текущей среде нет. Поэтому успешная сборка и требования `K8S-001`, `APP-001`, `GW-001–004`, `DEP-001–002` и работа сетевого пути остаются без фактического подтверждения. Метрики Prometheus, сборщик Fluentd, панель и операции релиза добавляются следующими этапами.
