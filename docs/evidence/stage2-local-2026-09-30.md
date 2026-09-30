# Этап 2: локальные проверки конфигурации

Дата: 30 сентября 2026. Среда: macOS ARM64, Python 3.14.5, Ruby 2.6.10. Registry manifests проверены Docker CLI через сеть; Docker daemon, живая Ubuntu VM и Kubernetes context отсутствуют. Эти результаты подтверждают файлы и архитектуру образов, но не подтверждают работу кластера.

## Пройдены

Первый тест marker-парсера запускался до реализации. Он завершился ожидаемым `FAIL` на assertion: CRI JSON не распознавался заглушкой. После реализации тесты прошли. Отдельная проверка доказала, что прежнее условие ошибочно принимало `event=error`; после фикса marker принимается только из `event=access`.

`python3 -m unittest tests.test_observability`:

```text
Ran 2 tests
OK
```

`python3 -m unittest discover -s tests -p 'test_*.py'`:

```text
Ran 7 tests in 3.545s
OK
```

Проверка охватывает CRI строку с JSON, выбранную версию, только access-событие и поиск маркера в файле Fluentd.

`bash -n scripts/bootstrap.sh scripts/deploy.sh scripts/verify.sh && git diff --check`: код завершения `0`, вывода нет.

`ruby -e 'require "yaml"; ARGV.each { |path| YAML.load_stream(File.read(path)); puts "YAML OK: #{path}" }' deploy/base.yaml deploy/envoy-proxy.yaml deploy/gateway.yaml deploy/route.yaml deploy/observability.yaml deploy/prometheus.yml`:

```text
YAML OK: deploy/base.yaml
YAML OK: deploy/envoy-proxy.yaml
YAML OK: deploy/gateway.yaml
YAML OK: deploy/route.yaml
YAML OK: deploy/observability.yaml
YAML OK: deploy/prometheus.yml
```

Через `docker manifest inspect --verbose IMAGE` проверены ARM64 descriptors и закреплены отдельные ARM64 digests:

| Образ | ARM64 digest |
| --- | --- |
| `prom/prometheus:v3.14.0` | `sha256:2d25f68eb7aa2e654dadd83b45e5757259b32a1e4b6bc370f1eec927f491265b` |
| `fluent/fluentd:v1.19.3-debian-2.2` | `sha256:5b3b1325f180f75e2c41672d03d30f3a26440d34667c49d6b9b0f9e5b766d734` |
| `quay.io/prometheus/node-exporter:v1.12.1` | `sha256:c9ef89f9464f09e7234decaae68a80ab856ff0014435677a99fd48b03dd410ea` |
| `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.20.0` | `sha256:92b46557c71ecac53825772e4827dbcd9fca876b1950060f8fb2f2ef0d7a27af` |

Release tags сверены с upstream: Prometheus 3.14.0; Fluentd Docker image 1.19.3; node-exporter 1.12.1; kube-state-metrics 2.20.0. Версии записаны в `deploy/versions.env`. Проверены upstream сведения, что Envoy Gateway 1.9 proxy metrics доступны на `19001/stats/prometheus`, а kube-state-metrics принимает ограничение `--resources`.

## Решение и ограничения

Файловый `timekey` установлен в 10 секунд с 1-секундным ожиданием и интервалом flush 2 секунды, чтобы сквозная проверка могла найти marker максимум за 30 секунд. Это отступление от запланированных почасовых файлов: при постоянной нагрузке появится больше небольших файлов. CronJob каждый час удаляет только закрытые `trafficops*.log` старше 24 часов; буфер Fluentd расположен вне `/logs`. Фактическую ротацию, отсутствие удаления активных chunks и скорость появления записи без VM проверить не удалось.

Local PV объявляет 2 GiB, но `local.path` на host filesystem не создаёт дисковую квоту. Пропускная способность, потребление RAM/диска, Fluentd configuration parsing, Prometheus `promtool check config`, Kubernetes admission, scrape targets и запрос через Gateway здесь не проверялись. Образы не скачивались и не собирались. Отсутствие Docker daemon зафиксировано ранее в [этапе 1](stage1-local-2026-09-30.md); `docker manifest inspect` для этого этапа работал без daemon.

Поэтому MON-001/002, LOG-001/002, APP-003, DEP-006 и DOC-004 в [таблице приёмки](../requirements/06-acceptance.md) имеют статус `частично`.
