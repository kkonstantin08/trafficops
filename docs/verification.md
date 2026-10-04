# Проверка TrafficOps на Ubuntu Server 24.04

Инструкция предназначена для generic Ubuntu Server 24.04 VM или узла с доступом `sudo` и интернетом. Команды можно выполнять в локальном терминале VM или через SSH; UTM — только один из возможных способов запустить VM. Приведённые ниже шаги описывают воспроизведение, а ссылки на уже выполненные проверки отдельно указывают их фактические результаты.

## 1. Подготовка

Сначала проверьте гостевую ОС и ресурсы:

```bash
cat /etc/os-release
dpkg --print-architecture
uname -m
nproc
grep MemTotal /proc/meminfo
free -h
df -h /
```

Для основного acceptance требуется Ubuntu **24.04**. Поддерживаемые пары архитектур:

- `dpkg --print-architecture=amd64` и `uname -m=x86_64`;
- `dpkg --print-architecture=arm64` и `uname -m=aarch64`.

Скриптовые preflight guards требуют минимум 2 CPU и 3 GiB общей RAM по `MemTotal`; это пороги допуска bootstrap, а не гарантия достаточности памяти для любой нагрузки. Успешная clean-room AMD64 acceptance VM имела Ubuntu 24.04.4 LTS, 4 CPU, `MemTotal=4015132 KiB` (около 3.8 GiB), swap 0 и root filesystem 58 GB. Это конфигурация проведённой проверки, а не обязательный minimum ([preflight и bootstrap evidence](evidence/amd64-clean-bootstrap-2026-10-03.md)).

После полного deploy и повторного запуска на этой VM наблюдалось около 1.7–1.8 GiB used и 2.0–2.1 GiB available RAM; на root filesystem было занято около 5.4 GB из 58 GB. OOM matches за проверенные 20 минут отсутствовали. Это snapshot конкретной VM, не capacity guarantee или длительный soak/load test ([idempotence evidence](evidence/amd64-idempotence-2026-10-03.md)).

Перед установкой при необходимости сохраните snapshot средствами гипервизора. Bootstrap устанавливает компоненты, отключает swap и создаёт Kubernetes; не запускайте его на VM с чужим кластером.

## 2. Получение проекта и запуск

На Ubuntu Server 24.04 выполните основной путь установки:

```bash
sudo apt-get update
sudo apt-get install -y git make curl
git clone https://github.com/kkonstantin08/trafficops.git
cd trafficops
make bootstrap
make deploy
make verify
```

На момент этой документации AMD64 clean-room результат и эти изменения находятся в `fix/amd64-bootstrap`; ветка ещё не слита в `main`. Команды описывают текущую проверенную реализацию этой ветки и не утверждают, что default `main` уже содержит финальную реализацию.

Clean bootstrap был выполнен на новой Ubuntu 24.04.4 AMD64 VM: Docker/containerd, kubeadm/kubelet/kubectl и Helm изначально отсутствовали; вручную были установлены только `git`, `make`, `curl`. `make bootstrap` завершился с exit 0, node стал Ready, Flannel/CoreDNS были healthy; ручных исправлений не было ([bootstrap evidence](evidence/amd64-clean-bootstrap-2026-10-03.md)).

`make deploy` проверяет совпадение архитектуры host и единственного Kubernetes node, собирает образ внутри Ubuntu VM и импортирует его в containerd. `make deploy` завершился с exit 0; встроенный verify и отдельный `make verify` прошли. GatewayClass был Accepted, Gateway Accepted/Programmed, HTTPRoutes Accepted/ResolvedRefs; через Gateway получен HTTP 200, Fluentd marker найден, пять Prometheus jobs имели свежие `up=1`, health panel/controller вернул HTTP 200 ([deploy/verify evidence](evidence/amd64-clean-deploy-verify-2026-10-03.md)).

Jammy developer-only path: на Ubuntu 22.04 вместо `make bootstrap` используйте `make bootstrap-dev`. Он не является основной acceptance средой и не заменяет проверки на Ubuntu 24.04.

Для дальнейших ручных команд используйте kubeconfig проекта:

```bash
export KUBECONFIG="$HOME/.kube/trafficops.conf"
kubectl get nodes -o wide
kubectl get pods -A
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
printf 'Панель: http://%s:30080/\n' "$NODE_IP"
```

Ожидаются Ready у узла и готовые Deployments приложения, Gateway, Prometheus и управляющего API; Fluentd и node-exporter работают как DaemonSet. Готовность pod сама по себе не заменяет следующие проверки.

## 3. Панель и вход

Откройте напечатанный адрес в браузере машины, которая может подключиться к Ubuntu VM по TCP 30080. Если страница недоступна, проверьте `hostname -I` в VM, маршрутизацию и firewall/security-group правила среды. Локальная UTM сеть может потребовать дополнительную настройку, но UTM не обязательна. Вход требует **того же IP и порта**, которые напечатаны при установке: управляющий API проверяет Origin.

Пароль хранится вне репозитория:

```bash
PASSWORD_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/trafficops/admin-password"
stat -c '%a %n' "$PASSWORD_FILE"
cat "$PASSWORD_FILE"
```

Файл создаётся с mode `0600`; повторный deploy существующий пароль не меняет. Secret Kubernetes содержит PBKDF2 hash, не исходный пароль. Убедитесь, что `stat` выводит `600`, затем введите пароль в диалоге «Войти». Не включайте пароль, cookie или CSRF token в снимки экрана и отчёты. Без входа панель доступна для просмотра, управляющие действия запрещены.

Cookie устанавливается с `HttpOnly` и `SameSite=Strict`. `Secure=false` для текущего HTTP demo; не выставляйте его в недоверенную сеть. Все управляющие POST требуют точного разрешённого Origin, session и CSRF. Suite с 25 live negative requests через Gateway подтвердил missing/wrong Origin, неверный/oversized пароль, аутентификацию, ограничения параметров, CSRF, logout и отказ старой session после logout ([security evidence](evidence/amd64-security-negative-2026-10-03.md)). Это не полноценный penetration test.

Панель содержит разделы «Обзор», «Трафик», «Релизы», «Инциденты», «Диагностика». При недоступных метриках должны отображаться неопределённость и причина, а не нулевая доля ошибок. В новом AMD64 clean-room evidence проверены HTTP health/API ответы, но browser visual verification панели намеренно не выполнялась.

RBAC ограничивает HTTPRoute `demo-route` get/patch по `resourceNames`, Deployments `demo-v1`/`demo-v2` — get по `resourceNames`, ConfigMap `demo-v2-config` — get/patch по `resourceNames`. Для pod recovery ServiceAccount имеет `get/list/delete pods` без `resourceNames` в namespace `trafficops`. Controller application logic фильтрует demo pods, но Kubernetes RBAC не применяет этот label selector к `delete`: технически разрешено удалить любой pod в namespace. Это известное least-privilege ограничение, проверенное через `kubectl auth can-i`; реальные delete-запросы в RBAC suite не выполнялись ([RBAC evidence](evidence/amd64-rbac-2026-10-03.md)).

## 4. Полный HTTP-путь и собранные логи

Выполните контрольный запрос с новым маркером:

```bash
MARKER="manual-$(date +%s)"
curl --fail-with-body -H 'Host: trafficops.local' \
  -H "X-Request-ID: $MARKER" -H 'X-Run-ID: manual' \
  "http://${NODE_IP}:30080/demo/region/east"
```

В исходном состоянии ожидается HTTP 200 и JSON с `service=trafficops-demo`, `version=v1`, `region=east` и тем же `request_id`. Найдите маркер в «Диагностике» панели. Источник записей — файлы назначения Fluentd, а не прямой `kubectl logs` приложения.

Ручная проверка точки назначения:

```bash
kubectl exec -n observability daemonset/fluentd -- \
  /bin/sh -c 'grep -hF "$1" /logs/trafficops.*.log' sh "$MARKER"
```

Ожидается JSON access-запись с этим маркером. Для первой доставки допускается до 30 секунд; `make verify` выполняет ограниченное ожидание автоматически. В чистом AMD64 deploy контрольный маркер был найден в destination Fluentd ([deploy/verify evidence](evidence/amd64-clean-deploy-verify-2026-10-03.md)).

## 5. Фактические метрики

В отдельном терминале VM:

```bash
export KUBECONFIG="$HOME/.kube/trafficops.conf"
kubectl port-forward -n observability service/prometheus 19090:9090 --address=localhost
```

В основном терминале:

```bash
curl --fail --get http://localhost:19090/api/v1/query --data-urlencode 'query=up'
curl --fail --get http://localhost:19090/api/v1/query \
  --data-urlencode 'query=trafficops_http_requests_total'
curl --fail --get http://localhost:19090/api/v1/query \
  --data-urlencode 'query=timestamp(trafficops_http_requests_total)'
```

Проверьте `status=success`, targets двух версий приложения, Envoy, node-exporter и kube-state-metrics со значением `up=1`, счётчик после контрольного запроса и свежую исходную временную метку. Время выполнения query не доказывает свежесть исходных samples. В AMD64 `make verify` и независимых PromQL captures все пять jobs были `up=1` с непустыми свежими samples ([deploy/verify evidence](evidence/amd64-clean-deploy-verify-2026-10-03.md)). Завершите port-forward через Ctrl+C.

## 6. Релиз и автоматический откат

1. Убедитесь, что ошибки v2 выключены. Запустите серию трафика: 10 запросов/с, 180 секунд, `/demo`.
2. Начните пробный релиз. Ожидаемые веса — v1 90%, v2 10%.
3. Дождитесь полного окна 60 секунд и минимум 30 запросов v2. Решение здорового релиза должно показывать свежие samples и долю ошибок не выше 5%.
4. Завершите релиз; подтвердите запросом через Gateway ответ v2. Выполните ручной откат и подтвердите v1.
5. Повторно начните canary и включите демонстрационные ошибки v2. Если предыдущая серия закончилась, запустите новую.
6. После полного окна и двух последовательных проверок с долей 5xx больше 5% ожидаются автоматический откат, веса 100/0, причина и показатели в журнале, подтверждённый HTTP-ответ v1.
7. Выключите ошибки v2 и остановите трафик. Новый canary после отката начинается только вручную.

ConfigMap передаётся приложению через Kubernetes volume: включение и выключение ошибок может задержаться до обновления проекции. Не считайте нажатие кнопки доказательством того, что v2 уже возвращает 500.

`make verify-scenario` автоматизирует ограниченный сценарий через API и возвращает стенд к здоровому режиму v1. Выполняйте его без параллельных управляющих действий в панели.

На AMD64 после controller idle-timeout fix полный scenario завершился exit 0: из начальных 100/0 прошёл healthy 90/10 canary с полным свежим окном и достаточными v2 requests, completion до v2=100 и Gateway HTTP 200/v2; ручной rollback подтвердил v1. Затем fault injection вызвал реальные v2 HTTP 5xx; две последовательные свежие проверки выше 5% привели к автоматическому rollback, подтверждённому как HTTP v1 и веса 100/0. Cleanup остановил traffic, выключил ошибки и вернул маршрут к v1; ручных runtime fixes не было ([AMD64 scenario evidence](evidence/amd64-scenario-fix-2026-10-03.md)).

При расследовании предыдущего transient `503 UC` наиболее вероятной причиной по собранным данным признан upstream connection reuse около keep-alive boundary; это не доказательство единственной причины. Функциональная ревизия `0d5a2019b5c1bfc1e93e8af7de4f35b4a715326f` согласовала Uvicorn keep-alive 30s и Envoy panel-route idle timeout 15s; regression checks и 85/85 повторных Gateway requests прошли ([fix evidence](evidence/amd64-scenario-fix-2026-10-03.md)).

## 7. Восстановление и повторный запуск

Controller application logic выбирает demo pod по label selector и проверяет новый Ready pod и ответ приложения через Gateway. Однако Kubernetes RBAC даёт ServiceAccount `delete pods` на весь namespace `trafficops` без `resourceNames`; этот grant технически позволяет удалить любой pod этого namespace, а кодовый фильтр не сужает RBAC permission. Не используйте ServiceAccount controller для произвольного удаления pod. Live RBAC suite проверил разрешения без реальных delete-запросов; AMD64 pod recovery action повторно не выполнялась. Исторический пользовательский скриншот recovery относится к ARM64 VM ([RBAC evidence](evidence/amd64-rbac-2026-10-03.md), [историческая проверка панели](evidence/vm-ui-check-2026-10-01.md)).

Для проверки сохранности состояния controller API:

```bash
kubectl rollout restart deployment/trafficops-controller -n trafficops
kubectl rollout status deployment/trafficops-controller -n trafficops --timeout=180s
make verify
```

Журнал должен сохраниться. Прерванные операции не должны становиться успешными. При несовпадении фактического маршрута и SQLite панель показывает необходимость сверки; выполните ручной откат.

Затем повторите:

```bash
make bootstrap
make deploy
make verify
```

Для Jammy developer-only режима вместо `make bootstrap` используйте `make bootstrap-dev`. На Ubuntu 24.04 AMD64 повторные `make bootstrap → make deploy → make verify` завершились успешно; сохранились node UID, route UID, пароль панели, три PV и три PVC, operation journal, release/traffic state и веса 100/0. Verify снова подтвердил Gateway HTTP 200/v1, свежие Prometheus samples и Fluentd marker. Это доказательство повторного запуска на задокументированной конфигурации; bootstrap/deploy не являются командами сброса релиза ([idempotence evidence](evidence/amd64-idempotence-2026-10-03.md)).

## 8. Если проверка остановилась

```bash
kubectl get pods -A -o wide
kubectl get events -A --sort-by=.metadata.creationTimestamp
kubectl describe gateway trafficops -n trafficops
kubectl describe httproute demo-route -n trafficops
kubectl logs deployment/trafficops-controller -n trafficops --tail=100
kubectl logs deployment/prometheus -n observability --tail=100
kubectl logs daemonset/fluentd -n observability --tail=100
free -h
df -h /var/lib/trafficops
```

Сохраните ошибку и эти данные. Не применяйте `kubeadm reset` и не удаляйте local PV для восстановления: в них находятся метрики, логи и SQLite. После исправления причины можно повторить deploy. При проблеме canary сначала используйте ручной откат, который не зависит от Prometheus.

## 9. Что сохранить как доказательство

Дата, вывод версии ОС и обеих архитектурных команд, CPU/MemTotal/disk, commit SHA (`git rev-parse HEAD`), exit code bootstrap/deploy/verify и повторного запуска, HTTP JSON с маркером, Prometheus query со свежими samples, запись маркера в destination Fluentd и operation journal automatic rollback. Для оценки ресурсов сохраните `kubectl top pods -A`, если metrics-server установлен; он не является зависимостью проекта. Без него используйте `free -h`, `df -h /` и фактические метрики node-exporter. Не добавляйте пароль, cookie, CSRF, token или приватные IP в evidence.

Ссылки на уже сохранённые результаты: [clean AMD64 bootstrap](evidence/amd64-clean-bootstrap-2026-10-03.md), [deploy/verify](evidence/amd64-clean-deploy-verify-2026-10-03.md), [full scenario и controller fix](evidence/amd64-scenario-fix-2026-10-03.md), [idempotence](evidence/amd64-idempotence-2026-10-03.md), [HTTP security negative suite](evidence/amd64-security-negative-2026-10-03.md), [RBAC boundary suite](evidence/amd64-rbac-2026-10-03.md). Новая AMD64 browser visual verification не выполнялась.

Стенд одноузловой: local PV переживают перезапуск pod, но не потерю диска VM. Указанная capacity PV не обеспечивает дисковую квоту. Проверяйте свободное место и фактический расход памяти.
