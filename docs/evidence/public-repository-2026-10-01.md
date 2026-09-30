# Публичный репозиторий и CI

Дата фиксации: 1 октября 2026, Europe/Moscow. Агент работал на macOS ARM64. Установка в VM не выполнялась.

- Репозиторий: https://github.com/kkonstantin08/trafficops
- GitHub API подтвердил `isPrivate=false`, основную ветку `main`.
- Локальная main получила исходники через fast-forward; full unittest на main: `Ran 31 tests in 8.055s`, `OK`.
- Временный чистый HTTPS clone выполнен с отключёнными global/system Git config, credential helper, extra HTTP headers и интерактивным запросом credentials; GH_TOKEN/GITHUB_TOKEN удалены из окружения. Результат: `Unauthenticated public clone: OK; branch=main; SHA=c450e1ed9ff8bc1ae9b13a94d758fdf9311b8029`.
- Просмотрены tracked исходники и механизм генерации credentials вне репозитория; проверка всей локальной истории на шаблоны private keys, GitHub/API tokens: `no matches`. Реальные credentials не создавались и не раскрывались.

## GitHub Actions

[Успешный запуск 36775869932](https://github.com/kkonstantin08/trafficops/actions/runs/36775869932) для `c450e1ed9ff8bc1ae9b13a94d758fdf9311b8029`. Завершён 30 сентября 2026 в 20:56:03 UTC. Job `validate`: success, все проверочные и build steps: success.

Фактические строки журнала:

```text
Ran 31 tests in 8.673s
Summary: 36 resources found in 7 files - Valid: 36, Invalid: 0, Errors: 0, Skipped: 0
```

Workflow использовал runner Ubuntu 24.04, Python 3.12.12, Node 22.20.0, QEMU/Buildx. Step `Build AMD64 and ARM64 images without publishing` завершился успешно для `linux/amd64,linux/arm64`. Образ не публиковался в registry.

Это подтверждает публичный source clone, unit/syntax/schema checks и сборку образа. CI не создавал Kubernetes и не запускал Gateway/Prometheus/Fluentd: наличие Ubuntu runner не закрывает DEP-001. Реальные пути запроса, доставка логов, canary, расход ресурсов и повторное развёртывание остаются открытыми. Пользователь тестирует на Ubuntu 22.04.5 через `make bootstrap-dev`.

Следующий commit обновляет только документацию и PDF, с `[skip ci]`: исполняемый код и зависимости остаются теми же, что в указанном успешном CI.
