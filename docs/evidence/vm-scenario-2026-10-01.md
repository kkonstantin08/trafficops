# Canary и откат в пользовательской VM

Дата получения: 1 октября 2026, Europe/Moscow. Пользователь предоставил вывод `make verify-scenario` из ранее проверенной Ubuntu 22.04.5 ARM64 VM. Агент напрямую к VM не подключался; точная Git-ревизия и сырые samples не предоставлены.

```text
Resetting demo-v2 error switch; waiting 130 seconds for ConfigMap projection.
Running healthy canary with 20 requests/s for at most 180 seconds.
Healthy canary has a complete fresh window with at least 30 v2 requests.
Healthy release completed and HTTP v2 was confirmed through Gateway.
Manual rollback confirmed HTTP v1 through Gateway.
Enabling controlled v2 errors and running a failed canary.
Failed canary automatically rolled back; its fresh 5xx decision and HTTP v1 were confirmed.
Scenario passed; finally stopped traffic, disabled v2 errors, manually rolled back, and logged out.
```

Просмотренная реализация `scripts/verify-scenario.py` проверяет политику canary, безопасное начальное состояние, заполненное свежее окно с достаточным числом запросов v2, завершение здорового релиза и HTTP v2, ручной rollback и HTTP v1. Для ошибочного canary проверяются свежие показатели 5xx, решение автоматического отката, запись успешной операции в журнале и HTTP v1. Итоговая строка выдаётся только после успешной очистки: остановки трафика, отключения ошибок, ручного отката и logout.

Подтверждён сценарий traffic split и управления релизом для OPT-001; часть OPT-005 — авторизованный API, контролируемые ошибки и автоматический откат — проверена в VM. Отдельные негативные проверки Origin/CSRF и восстановление pod в этом сценарии не выполняются, поэтому OPT-005 остаётся частично. Повторный deploy (DEP-005) и запуск на Ubuntu 24.04 (DEP-001) остаются открытыми.
