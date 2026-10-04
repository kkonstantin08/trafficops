# Финальная проверка паспорта — 4 октября 2026

## Source

Main до passport commit: `8c3f6e5f0c4bf3b47b73b4501152f31560d70293`. Source: [docs/passport.md](../passport.md); generator: [build-passport.py](../../scripts/build-passport.py). Использован установленный Cyrillic-capable TTF, шрифт в Git не добавлялся.

## Output

[Паспорт.pdf](../../output/pdf/Паспорт.pdf), создан существующим ReportLab generator с детерминированными page breaks. Старый draft PDF удалён как устаревший.

## Checks

- File type: PDF 1.4, открывается PDF parser и Poppler renderer.
- File size: 52 363 bytes; меньше 15 MB.
- Page count: 3 A4 pages; меньше либо равно 4, пустой четвёртой страницы нет.
- Extracted text: PASS (pypdf); Cyrillic: PASS; stale/draft и AI/process language отсутствуют.
- Visual render: PASS; все три страницы отрендерены Poppler в PNG и просмотрены. Проверены margins, headings, таблица, diagram, footer, отсутствие overlap/clipping и читаемость шрифта 9–10 pt.
- Page 1: назначение, технологии/версии, Prometheus deployment и архитектурная схема.
- Page 2: обязательная часть с назначением и проверкой, улучшения, verification summary.
- Page 3: сильная сторона (2 предложения), сложное решение/альтернативы (3), каждый пункт развития (2); ограничения сохранены.

## Claims review

| Группа утверждений | Реализация / фактическое доказательство |
| --- | --- |
| Ubuntu, Kubernetes/containerd/Flannel, Envoy, platform pins | [versions.env](../../deploy/versions.env), [bootstrap](../../scripts/bootstrap.sh), [platform selector](../../scripts/platform.sh), [clean bootstrap](amd64-clean-bootstrap-2026-10-03.md) |
| Gateway resources, weighted v1/v2, NodePort, HTTP service и панель | [README](../../README.md), [demo](../../demo/app.py), [deploy](../../scripts/deploy.sh), [deploy/verify](amd64-clean-deploy-verify-2026-10-03.md) |
| Prometheus five jobs / 10s, Fluentd CRI marker, SQLite/local PV | [Prometheus config](../../deploy/prometheus.yml), [Fluentd config](../../deploy/fluent.conf), [controller store](../../controller/store.py), [deploy/verify](amd64-clean-deploy-verify-2026-10-03.md) |
| Canary policy, healthy completion, manual/automatic rollback и fault | [controller](../../controller/runtime.py), [full scenario после idle fix](amd64-scenario-fix-2026-10-03.md) |
| Повторный запуск и сохранение состояния | [idempotence](amd64-idempotence-2026-10-03.md) |
| PBKDF2, Origin/CSRF, cookies, bounded inputs, RBAC scope | [API](../../controller/api.py), [controller manifest](../../deploy/controller.yaml), [25 HTTP negative requests](amd64-security-negative-2026-10-03.md), [34 RBAC checks](amd64-rbac-2026-10-03.md) |
| Pod recovery: только историческая ARM64 live проверка | [старое recovery evidence](vm-ui-check-2026-10-01.md); свежая AMD64 проверка не заявлена |
| 41 tests, 37 manifests, multiarch build | [main CI 37192333821](https://github.com/kkonstantin08/trafficops/actions/runs/37192333821) |
| Main promotion и публичный default clone | [main finalization](main-finalization-2026-10-04.md) |

Работающие claims сверены с implementation и существующим live/CI evidence; направления развития явно будущие. Новая AMD64 browser visual verification не заявлена. Ограничения single-node/no HA, local PV, HTTP/no TLS, namespace-wide pod delete, transitive APT pins и visual UI gap сохранены. Новые runtime VM tests не выполнялись; submission bundle не создавался.

## Result

**PASS.** DOC-007–010 покрыты финальным паспортом и проведённой проверкой.
