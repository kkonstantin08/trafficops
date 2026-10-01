# Новое подтверждение ОС от пользователя

1 октября 2026, Europe/Moscow. После журналов с Ubuntu 22.04 пользователь предоставил новый вывод `/etc/os-release` и `kubectl get nodes -o wide`:

```text
PRETTY_NAME="Ubuntu 24.04.5 LTS"
VERSION_ID="24.04"
VERSION="24.04.5 LTS (Noble Numbat)"
VERSION_CODENAME=noble
UBUNTU_CODENAME=noble
ubuntu Ready control-plane 36m v1.36.5 192.168.64.5 <none> Ubuntu 24.04.5 LTS 5.15.0-191-generic (arm64) containerd://2.3.6
```

Это пользовательское подтверждение текущей среды; агент не подключался к VM. Оно не меняет OS-IMAGE в ранее предоставленных журналах deploy/verify. Способ и время смены ОС не указаны. Для DEP-001 нужен полный запуск и сценарий проверки, связанный с новой средой, включая повторное развёртывание. До получения такого журнала DEP-001 остаётся не проверено.
