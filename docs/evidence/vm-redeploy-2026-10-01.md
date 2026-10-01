# Повторное развёртывание

1 октября 2026, Europe/Moscow. Источник — приложенный пользователем журнал первого deploy, verify, сценария canary и повторного `make deploy` с последующим `make verify`. Агент к VM не подключался. Точная Git-ревизия не указана.

Первый deploy собрал образ из Dockerfile и установил Envoy Gateway (Helm revision 1), приложение, наблюдаемость и контроллер. Повторный deploy использовал cache сборки; Envoy Gateway получил revision 2. HTTPRoute сохранил текущие веса; существующие PVC и Deployment контроллера остались unchanged. Журнал не содержит значения пароля.

Сквозная проверка внутри повторного deploy завершилась:

```text
Gateway response verified: HTTP 200, version v1, request_id verify-f9b92e8f40b140f58c7ed3fd99b76f29
Fluentd log verified within 30 seconds: request_id verify-f9b92e8f40b140f58c7ed3fd99b76f29, version v1
Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for v1
TrafficOps panel and controller health verified through direct VM IP: HTTP 200 / HTTP 200
```

Последующий отдельный verify также подтвердил Gateway, Fluentd и Prometheus (маркер `verify-1691203b29aa4f169c82c81f28bfecb0`); его заключительная строка health в приложении отсутствует. Успешная полная проверка внутри повторного deploy подтверждает сохранение работоспособности DEP-005. Сохранность конкретных старых записей SQLite и метрик отдельно не проверялась.

В таблицах узла приложенного журнала OS-IMAGE указан `Ubuntu 22.04.5 LTS`, kernel `5.15.0-191-generic (arm64)`, runtime `containerd://2.3.6`, Kubernetes `v1.36.5`. Пользователь сообщил Ubuntu 24.04, что противоречит этим строкам. До нового согласованного подтверждения версии ОС DEP-001 остаётся не проверено; журнал не переименовывается в доказательство Ubuntu 24.04.
