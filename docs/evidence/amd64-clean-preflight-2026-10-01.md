# AMD64 clean-room preflight

Источник: вывод SSH-терминала, предоставленный пользователем 3 октября 2026 года. Агент не подключался к VM и не выполнял на ней команды. Имя файла с датой `2026-10-01` сохранено по явному запросу пользователя; это не дата фактического снимка. В приветствии VM указано `Sat Oct 3 18:23:05 UTC 2026`.

## VM

| Параметр | Предоставленное значение | Проверка |
| --- | --- | --- |
| Ubuntu version | Ubuntu 24.04.4 LTS; `VERSION_ID=24.04`, Noble Numbat | PASS: Ubuntu 24.04 LTS |
| Architecture | `dpkg --print-architecture`: `amd64` | PASS |
| Kernel architecture | `uname -m`: `x86_64`; ядро из приветствия `6.8.0-100-generic` | PASS |
| CPU | `nproc`: `4` | PASS: минимум 2 |
| RAM | `free -h`: total `3.8Gi`, available `3.4Gi`, used `483Mi` | PASS: близко к 4 GB; 3.8 GiB примерно 4.08 GB, значение округлено |
| Disk/free space | `/dev/sda1`, `/`: размер `58G`, занято `2.0G`, свободно `56G`, использование `4%` | PASS: достаточный запас для планируемого стенда |

Swap: `0B`. Точное значение `MemTotal` в KiB и конфигурация выделенной гипервизором RAM не предоставлены; оценка памяти основана на округлённом total из `free -h`. Достаточность ресурсов под фактической нагрузкой ещё не проверена.

Предоставленные команды и их вывод (без адреса подключения и учётных данных):

```text
cat /etc/os-release
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo

echo "ARCH=$(dpkg --print-architecture)"
ARCH=amd64
echo "UNAME=$(uname -m)"
UNAME=x86_64
echo "CPUS=$(nproc)"
CPUS=4
free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       483Mi       3.4Gi       1.0Mi       262Mi       3.4Gi
Swap:             0B          0B          0B
df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  2.0G   56G   4% /
```

## State

По сообщению пользователя, это новая VM для clean-room проверки TrafficOps. Kubernetes/Docker/TrafficOps ещё не устанавливались в рамках этой проверки. Предоставленный preflight не содержит инвентаризации установленных пакетов: отсутствие ранее установленных компонентов независимо не проверено.

На этом этапе агент не запускал bootstrap, deploy, installation commands или другие команды на VM и не менял её состояние. Функциональный код, baseline main и статусы приёмки не изменяются; merge не выполняется.

## Target revision

- Branch: `fix/amd64-bootstrap`.
- Expected SHA будущего clean-room запуска: `e24aa05c9618d9bb462515371088b816b566eb1b`.
- Локальные branch и HEAD перед созданием этого evidence проверены и совпали с указанными значениями; рабочий каталог был чистым.
- Evidence commit является отдельным документальным потомком указанного SHA. Целевая ревизия запуска остаётся указанной выше.

## Result

**PASS** — по предоставленному выводу VM соответствует заявленным требованиям preflight: Ubuntu 24.04 LTS, amd64/x86_64, 4 CPU, около 4 GB RAM и 56G свободного системного диска.

Это PASS только проверки исходных параметров VM. Clean-room bootstrap → deploy → verify на AMD64 ещё не выполнен; DEP-001 и остальные требования работоспособности этим документом не закрываются.

Замечания: точный MemTotal не предоставлен; swap отсутствует; приветствие сообщает, что список обновлений старше недели. Эти замечания не нарушают заявленные критерии preflight. Обновление пакетов не выполнялось.
