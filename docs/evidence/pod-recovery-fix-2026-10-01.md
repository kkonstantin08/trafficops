# HTTP 504 при восстановлении pod

1 октября 2026. Скриншот пользователя показывает HTTP 504 после действия «Перезапустить pod»; раздел логов доступен. Успешное восстановление этим скриншотом не подтверждено.

В HTTPRoute панели отсутствовал явный timeout. [Документация Envoy Gateway](https://gateway.envoyproxy.io/docs/tasks/traffic/http-timeouts/) указывает default request timeout 15 секунд. Синхронная операция ожидает удаление и replacement pod до 60 секунд, затем выполняет HTTP probe до 5 секунд; Kubernetes API calls имеют timeout 5 секунд. Это создаёт окно, в котором Gateway прерывает ответ до завершения операции.

В `deploy/controller-route.yaml` заданы request/backendRequest timeout 100 секунд, ниже браузерного POST timeout 120 секунд. Таймаут не отключён; повторные DELETE-запросы автоматически не отправляются. В `controller/clients.py` replacement должен иметь condition Ready=True и не находиться в удалении; одного phase Running недостаточно. Результат операции содержит replacement_ready.

Два новых теста сначала падали, после изменения проходят: наличие timeout в маршруте и ожидание Ready вместо Running. Повторная проверка через Gateway в VM требуется после deploy; OPT-005 остаётся частично.

Локальные результаты на macOS: полный unittest — 34 теста за 8.118 секунды, OK; `scripts/validate_manifests.sh` — 36 ресурсов, Valid 36, Invalid 0, Errors 0, Skipped 0. `git diff --check` — exit 0. Это проверяет код и схемы, но не заменяет повторный pod recovery в VM.
