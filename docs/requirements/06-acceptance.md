# 06. Приёмка и доказательства

Одна строка — один обязательный ID из [01](01-core.md), [02](02-deployment.md), [03](03-documentation.md) или [04](04-submission.md). При реализации заменить `—` в двух последних столбцах ссылкой на конкретный файл/раздел и на сохранённый фактический результат (команда с выводом, журнал, снимок экрана или артефакт). Указывать среду и дату проверки. Статусы: `не проверено`, `выполнено`, `частично`, `не выполнено`. Конфигурация подтверждает реализацию, но не заменяет проверку. Для условного GW-002 можно приложить доказательство неприменимости.

## Компоненты

| ID | Контрольная проверка | Статус | Реализация | Доказательство |
| --- | --- | --- | --- | --- |
| K8S-001 | API и узлы кластера доступны | выполнено | [bootstrap](../../scripts/bootstrap.sh) | [clean bootstrap: Ubuntu 24.04.4 AMD64, node Ready](../evidence/amd64-clean-bootstrap-2026-10-03.md), [deploy/verify](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| APP-001 | HTTP-приложение запущено в кластере | выполнено | [Deployment и Service](../../deploy/base.yaml) | [clean deploy/verify: приложение работает на Ubuntu 24.04.4 AMD64](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| APP-002 | Статус и ответ совпадают с ожидаемыми | выполнено | [приложение](../../demo/app.py), [тесты](../../tests/test_demo.py) | [независимый verify: Gateway HTTP 200, version v1 и ожидаемый JSON](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| APP-003 | Контрольный запрос есть в access-логе приложения | выполнено | [JSON stdout-логи](../../demo/app.py), [проверка маркера](../../scripts/verify.sh) | [verify: access-маркер найден в Fluentd destination](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| APP-004 | Образ доступен публично либо собирается из репозитория | выполнено | [Dockerfile](../../Dockerfile), [публичный source](https://github.com/kkonstantin08/trafficops) | [публичный clone и CI build AMD64/ARM64 подтверждены](../evidence/public-repository-2026-10-01.md) |
| GW-001 | Open-source контроллер установлен и готов | выполнено | [установка Envoy Gateway](../../scripts/deploy.sh) | [clean deploy: Envoy Gateway установлен и готов](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| GW-002 | GatewayClass работает либо обоснованно не нужен | выполнено | [GatewayClass и параметры EnvoyProxy](../../deploy/envoy-proxy.yaml) | [GatewayClass trafficops: Accepted=True](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| GW-003 | Gateway и HTTPRoute приняты и ведут к Service | выполнено | [Gateway](../../deploy/gateway.yaml), [HTTPRoute](../../deploy/route.yaml) | [Gateway Programmed, HTTPRoutes Accepted/ResolvedRefs; запрос прошёл к приложению](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| GW-004 | Запрос через Gateway возвращает ожидаемый ответ | выполнено | [ограниченная проверка Gateway](../../scripts/verify.sh) | [независимый запрос через Envoy NodePort: HTTP 200, version v1](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| MON-001 | Prometheus видит доступный target и свежие samples | выполнено | [scrape-конфигурация и ограниченная проверка](../../deploy/prometheus.yml), [verify](../../scripts/verify.sh) | [все пять targets up, lastError пустой, samples свежие](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| MON-002 | PromQL возвращает фактические метрики | выполнено | [метрики приложения и примеры PromQL](../../README.md), [verify](../../scripts/verify.sh) | [фактические PromQL results и source timestamps для HTTP 200 counter](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| LOG-001 | Fluentd/Filebeat передаёт логи в точку назначения | выполнено | [Fluentd CRI-конфигурация](../../deploy/fluent.conf), [DaemonSet и local PV](../../deploy/observability.yaml) | [clean verify: Fluentd доставил access-запись контрольного запроса](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| LOG-002 | Запрос с маркером найден в собранных логах | выполнено | [bounded marker-поиск](../../scripts/find_log_marker.py), [verify](../../scripts/verify.sh) | [request_id контрольного HTTP-запроса найден в Fluentd destination](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |

## Среда и развёртывание

| ID | Контрольная проверка | Статус | Реализация | Доказательство |
| --- | --- | --- | --- | --- |
| DEP-001 | Полный сценарий проверен на Ubuntu 24.04 | выполнено | [требуемая ОС и bootstrap](../../README.md) | [clean Ubuntu 24.04.4 AMD64 bootstrap](../evidence/amd64-clean-bootstrap-2026-10-03.md), [deploy/verify](../evidence/amd64-clean-deploy-verify-2026-10-03.md), [passing scenario после исправления](../evidence/amd64-scenario-fix-2026-10-03.md), 3 октября 2026 |
| DEP-002 | Чистое развёртывание не использует инфраструктуру участника | выполнено | [последовательность установки](../../README.md) | [публичная ветка клонирована на чистую VM; bootstrap, deploy и verify выполнены без сервисов участника в runtime path](../evidence/amd64-clean-bootstrap-2026-10-03.md), [deploy/verify](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DEP-003 | Обязательная часть работает без специфических коммерческих сервисов | выполнено | [локальные Kubernetes и NodePort](../../README.md) | [Ubuntu 24.04.4 с одноузловым Kubernetes, Envoy Gateway, Prometheus и Fluentd; обязательный путь проверен на generic VM без provider-specific services](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DEP-004 | Развёртывание по инструкции проходит без ручного создания ресурсов | выполнено | [bootstrap](../../scripts/bootstrap.sh), [deploy](../../scripts/deploy.sh) | [clean bootstrap и первый deploy выполнены скриптами; ручных Kubernetes patches/fixes не было](../evidence/amd64-clean-bootstrap-2026-10-03.md), [deploy/verify](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DEP-005 | Второй запуск сохраняет работоспособность | выполнено | [повторный deploy и сохранение весов](../../scripts/deploy.sh) | [повторные bootstrap → deploy → verify: identity кластера, state и storage сохранены; verify PASS](../evidence/amd64-idempotence-2026-10-03.md), 3 октября 2026 |
| DEP-006 | Все зависимости и установка перечислены или автоматизированы | частично | [версии](../../deploy/versions.env), [deploy](../../scripts/deploy.sh), [bootstrap](../../scripts/bootstrap.sh), [lock](../../requirements.lock) | [clean installation PASS; Helm checksum и OCI digests закреплены, но транзитивные APT-пакеты `docker-ce-rootless-extras`, `docker-compose-plugin`, `kubernetes-cni` и `pigz` отдельно не pin-ятся](../evidence/amd64-clean-bootstrap-2026-10-03.md), 3 октября 2026 |

## Документация

| ID | Контрольная проверка | Статус | Реализация | Доказательство |
| --- | --- | --- | --- | --- |
| DOC-001 | В клоне есть все исходные материалы для запуска | выполнено | [исходники и конфигурация](../../README.md) | [чистый публичный clone `fix/amd64-bootstrap` и запуск из checkout на VM](../evidence/amd64-clean-bootstrap-2026-10-03.md), [первый deploy/verify](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DOC-002 | README описывает архитектуру, технологии и версии | частично | [архитектура и версии](../../README.md) | [README всё ещё утверждает, что clean-room AMD64 не выполнялся; это противоречит clean bootstrap/deploy evidence и требует обновления](../../README.md), [runtime evidence](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DOC-003 | README даёт среду, зависимости и шаги развёртывания | частично | [инструкция VM](../verification.md) | [README и runbook содержат устаревшее утверждение, что clean AMD64 запуск не выполнен; команды пройдены на VM, но документы не актуализированы](../../README.md), [clean run](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DOC-004 | Проверки Gateway, метрик и логов из README работают | выполнено | [команды проверки и запросы](../../README.md), [verify](../../scripts/verify.sh) | [make verify: Gateway HTTP 200, свежие Prometheus samples и access-маркер во Fluentd](../evidence/amd64-clean-deploy-verify-2026-10-03.md), 3 октября 2026 |
| DOC-005 | README описывает заявленные улучшения и ограничения | частично | [панель, canary, инциденты и границы проверки](../../README.md) | [README ещё не отражает AMD64 live results и неточно описывает pod delete как selective; фактический RBAC даёт namespace-wide `delete pods`](../../README.md), [RBAC evidence](../evidence/amd64-rbac-2026-10-03.md), 3 октября 2026 |
| DOC-006 | В публикуемом репозитории и истории нет секретов | частично | [генерация пароля вне Git и hash в Secret](../../scripts/deploy.sh) | [прошлая проверка истории относится к более ранней ревизии; актуальная история текущей ветки целиком повторно не сканировалась](../evidence/public-repository-2026-10-01.md), 1 октября 2026 |
| DOC-007 | Паспорт соответствует формату, страницам и размеру | частично | [черновик PDF](../../output/pdf/TrafficOps-passport-draft.pdf) | [черновик: 2 страницы, 31 КБ, обе страницы отрендерены и просмотрены](../evidence/orchestrator-local-2026-09-30.md) |
| DOC-008 | Паспорт содержит архитектуру и подтверждаемые функции | частично | [источник паспорта](../passport.md) | [архитектура и функции описаны, live-проверки явно отмечены открытыми](../evidence/orchestrator-local-2026-09-30.md) |
| DOC-009 | Паспорт содержит ревью и предложения развития | частично | [ревью и ограничения](../passport.md) | [ревью и следующие шаги внесены в черновик](../evidence/orchestrator-local-2026-09-30.md) |
| DOC-010 | Каждое заявление паспорта связано с реализацией и проверкой | частично | [источник паспорта и ID](../passport.md) | [ID и локальные доказательства указаны; финальный паспорт после live-приёмки](../evidence/orchestrator-local-2026-09-30.md) |

## Дополнительные возможности, заявленные проектом

Live-функции оцениваются по runtime evidence. Отдельную visual browser verification на AMD64 в этой проверке не выполняли; это ограничивает пункты, где требуется подтвердить отображение данных в панели.

| ID | Контрольная проверка | Статус | Реализация | Доказательство |
| --- | --- | --- | --- | --- |
| OPT-001 | Traffic split и panel route доступны по IP; веса v1/v2 меняются только фиксированным HTTPRoute | выполнено | [Gateway и routes](../../deploy/gateway.yaml), [контроллер](../../controller/clients.py) | [полный passing scenario: canary, v2 completion, ручной и автоматический rollback с подтверждением ответа через Gateway](../evidence/amd64-scenario-fix-2026-10-03.md), 3 октября 2026 |
| OPT-002 | CI проверяет код, конфигурации и сборку AMD64/ARM64 | выполнено | [GitHub Actions](../../.github/workflows/ci.yml), [последний CI до этого evidence commit](https://github.com/kkonstantin08/trafficops/actions/runs/37152998922) | [run 37152998922 завершился success на предыдущем branch HEAD `cdabc1b0b821d89a413667145df6d0877db17106`](https://github.com/kkonstantin08/trafficops/actions/runs/37152998922), [functional fix CI](https://github.com/kkonstantin08/trafficops/actions/runs/37148162533) |
| OPT-003 | Дополнительные Prometheus метрики и панель показывают фактические samples | частично | [PromQL и проверка исходных timestamp](../../controller/clients.py), [панель](../../web/index.html) | [Prometheus queries и свежие source timestamps подтверждены live](../evidence/amd64-clean-deploy-verify-2026-10-03.md); отображение в браузере подтверждалось только старым screenshot на другой VM, новая AMD64 visual browser verification не выполнялась ([старое evidence](../evidence/vm-ui-check-2026-10-01.md)), 3 октября 2026 |
| OPT-004 | Fluentd логи доступны из панели с CRI временем и поиском маркера | частично | [bounded чтение логов](../../controller/runtime.py), [Fluentd](../../deploy/fluent.conf) | [Fluentd delivery и marker search подтверждены live](../evidence/amd64-clean-deploy-verify-2026-10-03.md); отображение записей и CRI time в панели не проверялось визуально на AMD64, 3 октября 2026 |
| OPT-005 | Ограниченный API, Origin/CSRF, canary rollback и pod recovery | частично | [API](../../controller/api.py), [runtime](../../controller/runtime.py), [namespace RBAC](../../deploy/controller.yaml), [bounded live scenario](../../scripts/verify-scenario.py) | [scenario и automatic rollback PASS](../evidence/amd64-scenario-fix-2026-10-03.md), [25 HTTP security negative tests PASS](../evidence/amd64-security-negative-2026-10-03.md), [34 RBAC checks PASS](../evidence/amd64-rbac-2026-10-03.md); известное ограничение: ServiceAccount может удалить любой pod в namespace `trafficops`, а не только demo pod; AMD64 pod recovery action и visual UI повторно не проверялись. Старый screenshot recovery: [1 октября, ARM64 VM](../evidence/vm-ui-check-2026-10-01.md) |

## Сдача

| ID | Контрольная проверка | Статус | Реализация | Доказательство |
| --- | --- | --- | --- | --- |
| SUB-001 | Архив ZIP/RAR назван фамилией и не превышает 18 МБ | не проверено | — | — |
| SUB-002 | В архиве есть `Ссылка.txt` и `Паспорт.pdf` | не проверено | — | — |
| SUB-003 | TXT содержит только ссылку на актуальную ветку | не проверено | — | — |
| SUB-004 | Публичный `git clone` проходит без авторизации | выполнено | [публичный репозиторий](https://github.com/kkonstantin08/trafficops) | [чистый HTTPS clone без credentials: main](../evidence/public-repository-2026-10-01.md); [clean clone опубликованной ветки `fix/amd64-bootstrap`](../evidence/amd64-clean-bootstrap-2026-10-03.md), 3 октября 2026 |
| SUB-005 | Полное решение находится в основной ветке `main` | не выполнено | [основная ветка](https://github.com/kkonstantin08/trafficops/tree/main), [реализация в fix/amd64-bootstrap](https://github.com/kkonstantin08/trafficops/tree/fix/amd64-bootstrap) | `main` остаётся на `20e5d247b4b044cec80f1a3c3f03abd940c3574c`; перед этим documentation-only commit `fix/amd64-bootstrap` был на `cdabc1b0b821d89a413667145df6d0877db17106` и ещё не был merge в `main` (refs проверены 4 октября 2026) |
| SUB-006 | Срок уточнён, загрузка своевременна, ревизия после срока неизменна | не проверено | — | — |
| SUB-007 | Загрузка архива подтверждена страницей задания | не проверено | — | — |

Критерии `EVAL-*` не имеют статуса выполнения: баллы выставляет жюри. `PREF-*` и `OPT-*` не являются обязательными; проверку выбранного улучшения добавлять отдельной строкой с его стабильным `OPT-*` ID после выбора.

## Текущее состояние перед финализацией

- Clean Ubuntu 24.04 AMD64 bootstrap — PASS; deploy/verify — PASS; полный canary со здоровым завершением и автоматическим rollback после исправления controller idle timeout — PASS; idempotence — PASS; HTTP security negative tests — PASS; RBAC boundary tests — PASS.
- Новая AMD64 visual UI verification намеренно не выполнялась. README/runbook и паспорт ещё не актуализированы, submission bundle не подготовлен.
- `fix/amd64-bootstrap` не merge в `main`; `main` остаётся на `20e5d247b4b044cec80f1a3c3f03abd940c3574c`.
