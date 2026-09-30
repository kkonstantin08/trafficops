# Проверка оркестратором

Дата: 30 сентября 2026. Среда: macOS ARM64, Python 3.14. Kubernetes context не задан; Docker daemon недоступен. Проверки ниже подтверждают локальный код и файлы, не запуск на Ubuntu 24.04.

## Этапы 1–2

Проверены изменения `8323137`, `efaff7d`, `fde1dcc`: приложение, manifests, bootstrap/deploy/verify, поиск маркера и таблица приёмки.

Команды выполнены оркестратором после commit этапа 2:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
Ran 7 tests in 3.543s
OK

bash -n scripts/bootstrap.sh scripts/deploy.sh scripts/verify.sh
git diff --check HEAD^ HEAD
exit 0
```

Ruby YAML parser успешно разобрал `base.yaml`, `envoy-proxy.yaml`, `gateway.yaml`, `route.yaml`, `observability.yaml`, `prometheus.yml`. Это проверка синтаксиса YAML; Kubernetes admission и Prometheus/Fluentd configuration parsing не выполнены.

При просмотре исправлены: безусловный restart demo при повторном deploy, сброс весов HTTPRoute, отсутствие request timeout у обычных Kubernetes запросов, выбор Envoy metrics target по необязательному имени порта, проверка свежести по timestamp вычисления PromQL и поиск error вместо access-записи.

Исправление `7c4d0bc` различает чужой preexisting containerd config и default config, установленный пакетом, и задаёт sandbox image через схему containerd 2.x v3. Оркестратор просмотрел diff и выполнил `python3 -m unittest tests.test_bootstrap_containerd_config` (1/1), `bash -n scripts/bootstrap.sh` и `git diff --check 7c4d0bc^ 7c4d0bc` (exit 0). Runtime containerd в VM остаётся непроверенным.

## Текущая граница

Этап 3 в работе. Live-запуск VM, HTTP через Gateway, Prometheus samples, доставка Fluentd, два развёртывания и расход ресурсов не проверены. Пользователь подтвердил, что среда — локальная VM UTM; вывод ОС/CPU/RAM запрошен и ещё не получен.

## Этап 3 и документы этапа 4

Оркестратор прочитал API, Kubernetes/Prometheus clients, SQLite store, canary evaluator, runtime, RBAC и UI. На текущем коде выполнил полный unittest: `Ran 25 tests in 6.798s`, `OK` (macOS, Python 3.14). Проверки используют подставные cluster ответы и не подтверждают runtime Kubernetes. На последующем коде окончательные результаты фиксируются ниже.

В локальной панели через встроенный браузер Codex проверены пять разделов, отображение unavailable/unknown при отсутствии настоящих компонентов, вход и выход с одноразовыми тестовыми credentials, disabled управляющие кнопки в режиме просмотра. При ширине окна около 630 px исправлен перенос навигации; проверены screenshot и accessibility tree. Управляющие операции над настоящим кластером не запускались. Временный preview server остановлен, вкладка закрыта.

`docs/verification.md` содержит порядок действий в локальной VM, HTTP-маркер, query исходных timestamps, canary, восстановление и повторное развёртывание. Черновик паспорта `output/pdf/TrafficOps-passport-draft.pdf` создан reportlab в bundled runtime, отрендерен Poppler; обе страницы просмотрены визуально. Размер 31 КБ, две страницы. Это не финальный комплект сдачи: live-приёмка и публичный адрес отсутствуют.

### Финальная проверка этапа 3

После `12dc12c` оркестратор повторно выполнил весь набор: `Ran 28 tests in 8.038s`, `OK`. `bash -n` для bootstrap/deploy/verify/validate_manifests, `node --check web/app.js`, Ruby YAML parse всех восьми YAML/YML файлов и `git diff --check` завершились exit 0. Это достаточная локальная проверка этапа; runtime на Ubuntu остаётся открытым.

Независимый запуск `scripts/validate_manifests.sh` сначала обнаружил несовместимые флаги местного sha256sum; исполнитель заменил сравнение на stdlib hashlib. Повторный запуск загрузил инструменты/CRD, но kubeconform не смог разрешить raw.githubusercontent.com через DNS `[::1]:53`: `Summary: 36 resources ... Valid: 0, Invalid: 0, Errors: 36, Skipped: 0`. Это ошибка получения схем, не успешная schema validation и не доказательство невалидности ресурсов. Дальнейшая проверка CI будет зафиксирована отдельно.

### CI validation после исправления

После `6cf40d1` оркестратор просмотрел workflow и validator и самостоятельно выполнил `./scripts/validate_manifests.sh`: `Summary: 36 resources found in 7 files - Valid: 36, Invalid: 0, Errors: 0, Skipped: 0`, exit 0. Скрипт получает core-схемы curl по закреплённому Git commit и валидирует локально; Gateway/Envoy схемы извлечены из закреплённых CRD. Предыдущая DNS-блокировка устранена. Проверка схем не подтверждает admission/runtime кластера. GitHub Actions и multiarch build не запускались; Docker daemon на Mac отсутствует.

### Итоговая локальная проверка сценария

После `cdd3324` оркестратор прочитал CLI и README, самостоятельно выполнил `python3 scripts/verify-scenario.py --help`, `python3 -m py_compile scripts/verify-scenario.py`, `python3 -m unittest tests.test_verify_scenario -v` (1/1), `make -n verify-scenario` и `git diff --check`: exit 0. Скрипт хранится как executable (Git mode 100755). Итоговый полный набор: `Ran 29 tests in 8.010s`, `OK`.

Проверка cleanup доказывает попытку всех действий восстановления после первого отказа, но не фактическое восстановление кластера. Live-сценарий не выполнялся. Исходники сохраняются локально в ветке trafficops-implementation; main и внешняя публикация пока не обновлены. Перед приёмкой нужен вывод ОС/архитектуры/vCPU/RAM из VM пользователя.
