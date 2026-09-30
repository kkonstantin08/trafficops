# Проверка TrafficOps в локальной VM

Все команды установки выполняются в терминале Ubuntu VM. Mac используется для просмотра панели. Приведённый порядок ещё не является доказательством успешного запуска: результаты следует сохранить после выполнения.

## 1. Подготовка

Сначала проверьте гостевую ОС и ресурсы:

```bash
cat /etc/os-release
uname -m
nproc
free -h
df -h /
```

Для приёмки ожидаются Ubuntu **24.04**, `aarch64`, минимум 2 vCPU и 3 GiB общей гостевой памяти. Скрипт измеряет `MemTotal`, не свободную память. Текущая пользовательская VM сообщена как Ubuntu 22.04.5 ARM64, 4 vCPU, 3.8 GiB общей RAM и 2.9 GiB доступной; обычный bootstrap её не принимает. Чтобы тестировать без замены гостевой ОС, используйте отдельный dev режим ниже. Он не подтверждает требование DEP-001. Достаточность памяти всего стенда ещё необходимо измерить.

Перед установкой сохраните снимок VM средствами UTM. Bootstrap устанавливает компоненты, отключает swap и создаёт Kubernetes. Он не предназначен для VM с чужим кластером. Установка в VM — отдельный шаг пользователя после просмотра этой инструкции.

## 2. Получение проекта и запуск

Публичный адрес репозитория ещё не задан. До публикации скопируйте каталог проекта в VM; после публикации клонируйте репозиторий и перейдите в его корень.

```bash
sudo apt-get update
sudo apt-get install -y git make curl
# Перейдите в каталог, содержащий Makefile и scripts/.
make bootstrap
make deploy
make verify
```

Для тестов на текущей Ubuntu 22.04 ARM64 VM замените только первую команду на `make bootstrap-dev`. Этот явный режим ставит закреплённые ARM64 пакеты Docker для Jammy; `make bootstrap` по-прежнему принимает только Ubuntu 24.04. Дальнейшие `make deploy` и `make verify` те же. Установку в VM здесь не выполняли.

Не выполняйте эти команды на Mac. Сборка образа происходит внутри ARM64 VM. `make deploy` завершается проверкой, поэтому отдельный `make verify` позволяет сохранить результат повторного запроса.

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

Откройте напечатанный адрес сначала в браузере VM, затем на Mac. Для доступа с Mac сеть UTM должна позволять соединение с IP VM на TCP 30080. Если страница не открывается, проверьте `hostname -I` в VM и сетевой режим UTM. Вход требует **того же IP и порта**, которые напечатаны при установке: управляющий API проверяет Origin.

Пароль хранится вне репозитория:

```bash
cat "${XDG_CONFIG_HOME:-$HOME/.config}/trafficops/admin-password"
```

Введите его в диалоге «Войти». Не включайте пароль, cookie или CSRF token в снимки экрана и отчёты. Без входа панель доступна для просмотра, управляющие действия запрещены.

Проверьте разделы «Обзор», «Трафик», «Релизы», «Инциденты», «Диагностика». При недоступных метриках должны отображаться неопределённость и причина, а не нулевая доля ошибок.

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

Ожидается JSON access-запись с этим маркером. Для первой доставки допускается до 30 секунд; `make verify` выполняет ограниченное ожидание автоматически.

## 5. Фактические метрики

В отдельном терминале VM:

```bash
export KUBECONFIG="$HOME/.kube/trafficops.conf"
kubectl port-forward -n observability service/prometheus 19090:9090 --address=127.0.0.1
```

В основном терминале:

```bash
curl --fail --get http://127.0.0.1:19090/api/v1/query --data-urlencode 'query=up'
curl --fail --get http://127.0.0.1:19090/api/v1/query \
  --data-urlencode 'query=trafficops_http_requests_total'
curl --fail --get http://127.0.0.1:19090/api/v1/query \
  --data-urlencode 'query=timestamp(trafficops_http_requests_total)'
```

Проверьте `status=success`, targets приложения, Envoy, node-exporter и kube-state-metrics со значением `up=1`, счётчик после контрольного запроса и свежую исходную временную метку. Время выполнения query не доказывает свежесть исходных samples. Завершите port-forward через Ctrl+C.

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

## 7. Восстановление и повторный запуск

В панели удалите один демонстрационный pod. Операция должна подтвердить новый готовый pod и ответ приложения через Gateway. Для проверки сохранности состояния API:

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

Для Jammy повторите вместо `make bootstrap` команду `make bootstrap-dev`. Ожидается сохранение пароля, данных, работоспособности и текущих весов маршрута. Повторный deploy не является командой сброса релиза.

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

Дата, вывод версии ОС/архитектуры/ресурсов, commit SHA (`git rev-parse HEAD`), вывод первого и повторного запуска, HTTP JSON с маркером, Prometheus query со свежими samples, запись маркера в назначении Fluentd, журнал автоматического отката и итоговый ответ v1. Для оценки ресурсов сохраните `kubectl top pods -A`, если metrics-server установлен; он не является зависимостью проекта. Без него используйте `free -h`, `df -h` и фактические метрики node-exporter в Prometheus.

Стенд одноузловой: local PV переживают перезапуск pod, но не потерю диска VM. Указанная capacity PV не обеспечивает дисковую квоту. Проверяйте свободное место и фактический расход памяти.
