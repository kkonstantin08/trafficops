# AMD64 clean bootstrap — 3 октября 2026

## Environment

Проверка выполнена агентом через SSH на указанной пользователем новой VM; адрес и credentials исключены из evidence. Ubuntu 24.04.4 LTS (Noble), Debian architecture amd64, uname x86_64, ядро 6.8.0-100-generic. CPU: 4. MemTotal: 4015132 kB (KiB), free -h: 3.8Gi total. Swap: 0B. Системный диск /dev/sda1: 58G, занято 2.0G, свободно 56G (4%).

## Tested revision

- Repository: https://github.com/kkonstantin08/trafficops
- Branch: fix/amd64-bootstrap
- Exact SHA на VM: `6c611c46862061caba371b27b9df2e062f2753be`.
- Родитель: `e24aa05c9618d9bb462515371088b816b566eb1b`, согласованная AMD64 implementation revision. Единственное изменение поверх него до теста — документация preflight.
- Перед запуском локальный и remote HEAD совпали с ожидаемым SHA; clone на VM показал ту же ветку и SHA, git status --short был пустым.

## Initial state

Проверено 2026-10-03T18:32:34+00:00. Полный вывод команд исходной проверки:

```text
=== CLEAN STATE ===
2026-10-03T18:32:34+00:00
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
ARCH=amd64
UNAME=x86_64
CPUS=4
MemTotal:        4015132 kB
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       478Mi       3.4Gi       1.0Mi       265Mi       3.4Gi
Swap:             0B          0B          0B
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  2.0G   56G   4% /
=== EXISTING TOOLS ===
=== KUBERNETES STATE ===
NO KUBERNETES ADMIN.CONF
=== RELEVANT PACKAGES ===
=== TRAFFICOPS PATHS ===
=== CLEAN END ===
```

Команды: date -Is, cat /etc/os-release, dpkg --print-architecture, uname -m, nproc, grep MemTotal /proc/meminfo, free -h, df -h /. command -v для docker/containerd/kubeadm/kubelet/kubectl/helm не выдал путей; dpkg -l с фильтром docker|containerd|kubeadm|kubelet|kubectl|helm не выдал пакетов; /etc/kubernetes/admin.conf отсутствовал. Дополнительно find /root /opt /srv /home -maxdepth 3 -iname '*trafficops*' не нашёл путей. Это подтверждает clean state в границах этих проверок, не полную инвентаризацию всех файлов VM.

## Prerequisites

Вручную выполнены только:

```bash
sudo apt-get update
sudo apt-get install -y git make curl
git clone --branch fix/amd64-bootstrap --single-branch https://github.com/kkonstantin08/trafficops.git
cd trafficops
git branch --show-current
git rev-parse HEAD
git status --short
```

git уже был установлен (1:2.43.0-1ubuntu7.3), make установлен (4.3-4.1build2); curl обновлён до 8.5.0-2ubuntu10.15 вместе с libcurl4t64 и libcurl3t64-gnutls как зависимостями apt. apt upgrade не выполнялся. Docker/containerd/Kubernetes/Helm/CNI вручную не устанавливались. Apt сообщал debconf fallback Dialog → Readline; needrestart автоматически перезапустил packagekit.service при установке prerequisites, без вмешательства агента.

## Bootstrap

Exact command:

```bash
date -Is
set -o pipefail
make bootstrap 2>&1 | tee ~/trafficops-clean-bootstrap.log
bootstrap_exit=${PIPESTATUS[0]}
echo "BOOTSTRAP_EXIT=$bootstrap_exit"
date -Is
```

Start: 2026-10-03T18:33:26+00:00 (21:33:26 MSK).
End: 2026-10-03T18:34:38+00:00 (21:34:38 MSK).
**BOOTSTRAP_EXIT=0.**

Стадии: preflight → apt repositories/package installation → package holds → управляемая конфигурация containerd → Helm с checksum → Flannel manifest → sysctl/modules → kubeadm init → снятие control-plane taint → установка Flannel → ожидание Ready node и Available CoreDNS. Все эти действия выполнил bootstrap.

## Resulting versions

| Компонент | Фактическое значение |
| --- | --- |
| kubeadm / Kubernetes / kubelet / kubectl | v1.36.5, пакеты 1.36.5-1.1 |
| containerd | v2.3.6, пакет 2.3.6-1~ubuntu.24.04~noble |
| Docker | 29.8.1, build 4a63305; пакет 5:29.8.1-1~ubuntu.24.04~noble |
| Docker Buildx package | 0.37.1-1~ubuntu.24.04~noble |
| Helm | v3.22.0+g144ca65 |
| Flannel image | ghcr.io/flannel-io/flannel:v0.28.9 |
| Flannel CNI image | ghcr.io/flannel-io/flannel-cni-plugin:v1.9.1-flannel3 |

Основные версии соответствуют deploy/versions.env. Apt также установил docker-ce-rootless-extras 5:29.8.2-1~ubuntu.24.04~noble, docker-compose-plugin 5.6.0-1~ubuntu.24.04~noble, kubernetes-cni 1.9.1-1.1 и pigz 2.8-1. Эти транзитивные пакеты отдельно не закреплены в versions.env: замечание к воспроизводимости, не скрытая ручная установка.

## Kubernetes state

Один node vm-928254: Ready, control-plane, amd64, kubelet v1.36.5, runtime containerd://2.3.6. Все 8 pods Running, READY 1/1, RESTARTS 0. containerd/docker/kubelet active; systemctl --failed: 0 units. CrashLoopBackOff/ImagePullBackOff/Pending/NotReady в снимке отсутствуют. Проверены состояние компонентов и pinned Flannel images; отдельный межподовый сетевой тест в scope не входил.

## Resources

После bootstrap: RAM total 3.8Gi, used 1.1Gi, available 2.7Gi; swap 0B. Disk: 58G total, 3.6G used, 54G available, 7%. Это снимок после bootstrap, не доказательство запаса для всей системы под нагрузкой.

## Manual fixes

None.

## Result

**PASS.** Исходное состояние чистое по выполненным проверкам, вручную запрошены только git/make/curl, bootstrap exit 0, один amd64 node Ready, основные pods здоровы, ручных runtime fixes не было.

Существенные warnings/ограничения: rehash пропустил объединённый ca-certificates.crt, поскольку он содержит несколько сертификатов; CA update завершился, HTTPS downloads и bootstrap успешны. Приветствие до apt update сообщало устаревший список обновлений. Полное обновление ОС не выполнялось. BatchMode SSH probe первоначально завершился 255 (publickey,password); последующее подключение с предоставленным паролем успешно. Bootstrap failed commands не наблюдались.

## Scope

- make deploy ещё не выполнялся.
- make verify ещё не выполнялся.
- Приложение/Gateway/Prometheus/Fluentd этим этапом не проверены.
- Этот тест сам по себе ещё не закрывает весь DEP-002/004/006.
- main не изменялся; merge не выполнялся; acceptance/baseline не переписывались.
- Функциональный код не менялся.
- Полный исходный bootstrap transcript сохранён на VM в /root/trafficops-clean-bootstrap.log; он содержит bootstrap credentials и не публикуется в сыром виде. Ниже полная копия с заменой IP, bootstrap token и discovery hash. Временные progress carriage returns нормализованы при чтении; стадии/строки не сокращены.

## Post-bootstrap transcript

```text

NAME        STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
vm-928254   Ready    control-plane   59s   v1.36.5   [redacted-ip]   <none>        Ubuntu 24.04.4 LTS   6.8.0-100-generic (amd64)   containerd://2.3.6
NAMESPACE      NAME                                READY   STATUS    RESTARTS   AGE   IP               NODE        NOMINATED NODE   READINESS GATES
kube-flannel   kube-flannel-ds-xcfgs               1/1     Running   0          51s   [redacted-ip]   vm-928254   <none>           <none>
kube-system    coredns-589f44dc88-jqt2h            1/1     Running   0          50s   [redacted-ip]       vm-928254   <none>           <none>
kube-system    coredns-589f44dc88-kx88r            1/1     Running   0          50s   [redacted-ip]       vm-928254   <none>           <none>
kube-system    etcd-vm-928254                      1/1     Running   0          57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system    kube-apiserver-vm-928254            1/1     Running   0          57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system    kube-controller-manager-vm-928254   1/1     Running   0          57s   [redacted-ip]   vm-928254   <none>           <none>
kube-system    kube-proxy-8b98x                    1/1     Running   0          51s   [redacted-ip]   vm-928254   <none>           <none>
kube-system    kube-scheduler-vm-928254            1/1     Running   0          57s   [redacted-ip]   vm-928254   <none>           <none>
=== VERSIONS ===
v1.36.5
Client Version: v1.36.5
Kustomize Version: v5.8.1
containerd containerd v2.3.6 ee2735368117d2eb259779949d5e75cdafec9761
Docker version 29.8.1, build 4a63305
v3.22.0+g144ca65
=== NODE ===
name=vm-928254 arch=amd64 kubelet=v1.36.5 runtime=containerd://2.3.6
=== CONDITIONS ===
NAME        STATUS   ROLES           AGE   VERSION
vm-928254   Ready    control-plane   60s   v1.36.5
=== MEMORY AFTER BOOTSTRAP ===
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       1.1Gi       799Mi       2.4Mi       2.3Gi       2.7Gi
Swap:             0B          0B          0B
=== DISK AFTER BOOTSTRAP ===
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        58G  3.6G   54G   7% /
=== SERVICES ===
active
active
active
  UNIT LOAD ACTIVE SUB DESCRIPTION

0 loaded units listed.
=== PACKAGE VERSIONS ===
containerd.io 2.3.6-1~ubuntu.24.04~noble
docker-buildx-plugin 0.37.1-1~ubuntu.24.04~noble
docker-ce 5:29.8.1-1~ubuntu.24.04~noble
docker-ce-cli 5:29.8.1-1~ubuntu.24.04~noble
docker-ce-rootless-extras 5:29.8.2-1~ubuntu.24.04~noble
docker-compose-plugin 5.6.0-1~ubuntu.24.04~noble
kubeadm 1.36.5-1.1
kubectl 1.36.5-1.1
kubelet 1.36.5-1.1
kubernetes-cni 1.9.1-1.1
=== FLANNEL IMAGES ===
ghcr.io/flannel-io/flannel:v0.28.9
ghcr.io/flannel-io/flannel-cni-plugin:v1.9.1-flannel3 ghcr.io/flannel-io/flannel:v0.28.9
=== POST END ===

```

## Bootstrap transcript (sanitized)

```text

sudo ./scripts/bootstrap.sh
Hit:1 http://archive.ubuntu.com/ubuntu noble InRelease
Hit:2 http://archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:3 http://security.ubuntu.com/ubuntu noble-security InRelease
Hit:4 http://archive.ubuntu.com/ubuntu noble-backports InRelease
Reading package lists...
Reading package lists...
Building dependency tree...
Reading state information...
curl is already the newest version (8.5.0-2ubuntu10.15).
python3 is already the newest version (3.12.3-0ubuntu2.1).
python3 set to manually installed.
The following additional packages will be installed:
  dirmngr gnupg gnupg-l10n gnupg-utils gpg-agent gpg-wks-client gpgconf gpgsm
  gpgv keyboxd
Suggested packages:
  pinentry-gnome3 tor parcimonie xloadimage gpg-wks-server scdaemon
The following NEW packages will be installed:
  apt-transport-https
The following packages will be upgraded:
  ca-certificates dirmngr gnupg gnupg-l10n gnupg-utils gpg gpg-agent
  gpg-wks-client gpgconf gpgsm gpgv keyboxd
12 upgraded, 1 newly installed, 0 to remove and 200 not upgraded.
Need to get 2436 kB of archives.
After this operation, 17.4 kB disk space will be freed.
Get:1 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpg-wks-client amd64 2.4.4-2ubuntu17.6 [70.9 kB]
Get:2 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 dirmngr amd64 2.4.4-2ubuntu17.6 [323 kB]
Get:3 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpgsm amd64 2.4.4-2ubuntu17.6 [232 kB]
Get:4 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gnupg-utils amd64 2.4.4-2ubuntu17.6 [109 kB]
Get:5 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpg-agent amd64 2.4.4-2ubuntu17.6 [227 kB]
Get:6 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpg amd64 2.4.4-2ubuntu17.6 [565 kB]
Get:7 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpgconf amd64 2.4.4-2ubuntu17.6 [104 kB]
Get:8 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gnupg all 2.4.4-2ubuntu17.6 [359 kB]
Get:9 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 keyboxd amd64 2.4.4-2ubuntu17.6 [78.3 kB]
Get:10 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gpgv amd64 2.4.4-2ubuntu17.6 [158 kB]
Get:11 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 ca-certificates all 20260601~24.04.1 [139 kB]
Get:12 http://archive.ubuntu.com/ubuntu noble-updates/universe amd64 apt-transport-https all 2.8.3 [3970 B]
Get:13 http://archive.ubuntu.com/ubuntu noble-updates/main amd64 gnupg-l10n all 2.4.4-2ubuntu17.6 [66.5 kB]
Preconfiguring packages ...
Fetched 2436 kB in 2s (1074 kB/s)
(Reading database ... 
(Reading database ... 5%
(Reading database ... 10%
(Reading database ... 15%
(Reading database ... 20%
(Reading database ... 25%
(Reading database ... 30%
(Reading database ... 35%
(Reading database ... 40%
(Reading database ... 45%
(Reading database ... 50%
(Reading database ... 55%
(Reading database ... 60%
(Reading database ... 65%
(Reading database ... 70%
(Reading database ... 75%
(Reading database ... 80%
(Reading database ... 85%
(Reading database ... 90%
(Reading database ... 95%
(Reading database ... 100%
(Reading database ... 74870 files and directories currently installed.)
Preparing to unpack .../0-gpg-wks-client_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpg-wks-client (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../1-dirmngr_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking dirmngr (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../2-gpgsm_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpgsm (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../3-gnupg-utils_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gnupg-utils (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../4-gpg-agent_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpg-agent (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../5-gpg_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpg (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../6-gpgconf_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpgconf (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../7-gnupg_2.4.4-2ubuntu17.6_all.deb ...
Unpacking gnupg (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../8-keyboxd_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking keyboxd (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Preparing to unpack .../9-gpgv_2.4.4-2ubuntu17.6_amd64.deb ...
Unpacking gpgv (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Setting up gpgv (2.4.4-2ubuntu17.6) ...
(Reading database ... 
(Reading database ... 5%
(Reading database ... 10%
(Reading database ... 15%
(Reading database ... 20%
(Reading database ... 25%
(Reading database ... 30%
(Reading database ... 35%
(Reading database ... 40%
(Reading database ... 45%
(Reading database ... 50%
(Reading database ... 55%
(Reading database ... 60%
(Reading database ... 65%
(Reading database ... 70%
(Reading database ... 75%
(Reading database ... 80%
(Reading database ... 85%
(Reading database ... 90%
(Reading database ... 95%
(Reading database ... 100%
(Reading database ... 74870 files and directories currently installed.)
Preparing to unpack .../ca-certificates_20260601~24.04.1_all.deb ...
Unpacking ca-certificates (20260601~24.04.1) over (20240203) ...
Selecting previously unselected package apt-transport-https.
Preparing to unpack .../apt-transport-https_2.8.3_all.deb ...
Unpacking apt-transport-https (2.8.3) ...
Preparing to unpack .../gnupg-l10n_2.4.4-2ubuntu17.6_all.deb ...
Unpacking gnupg-l10n (2.4.4-2ubuntu17.6) over (2.4.4-2ubuntu17.4) ...
Setting up apt-transport-https (2.8.3) ...
Setting up ca-certificates (20260601~24.04.1) ...
Updating certificates in /etc/ssl/certs...
rehash: warning: skipping ca-certificates.crt,it does not contain exactly one certificate or CRL
14 added, 39 removed; done.
Setting up gnupg-l10n (2.4.4-2ubuntu17.6) ...
Setting up gpgconf (2.4.4-2ubuntu17.6) ...
Setting up gpg (2.4.4-2ubuntu17.6) ...
Setting up gnupg-utils (2.4.4-2ubuntu17.6) ...
Setting up gpg-agent (2.4.4-2ubuntu17.6) ...
Setting up gpgsm (2.4.4-2ubuntu17.6) ...
Setting up dirmngr (2.4.4-2ubuntu17.6) ...
Setting up keyboxd (2.4.4-2ubuntu17.6) ...
Setting up gnupg (2.4.4-2ubuntu17.6) ...
Setting up gpg-wks-client (2.4.4-2ubuntu17.6) ...
Processing triggers for install-info (7.1-3build2) ...
Processing triggers for man-db (2.12.0-4build2) ...
Processing triggers for ca-certificates (20260601~24.04.1) ...
Updating certificates in /etc/ssl/certs...
0 added, 0 removed; done.
Running hooks in /etc/ca-certificates/update.d...
done.

Running kernel seems to be up-to-date.

No services need to be restarted.

No containers need to be restarted.

No user sessions are running outdated binaries.

No VM guests are running outdated hypervisor (qemu) binaries on this host.
Get:1 https://download.docker.com/linux/ubuntu noble InRelease [48.5 kB]
Get:2 https://download.docker.com/linux/ubuntu noble/stable amd64 Packages [68.0 kB]
Get:3 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  InRelease [1227 B]
Hit:4 http://security.ubuntu.com/ubuntu noble-security InRelease
Get:5 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  Packages [9460 B]
Hit:6 http://archive.ubuntu.com/ubuntu noble InRelease
Hit:7 http://archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:8 http://archive.ubuntu.com/ubuntu noble-backports InRelease
Fetched 127 kB in 1s (221 kB/s)
Reading package lists...
Reading package lists...
Building dependency tree...
Reading state information...
The following additional packages will be installed:
  docker-ce-rootless-extras docker-compose-plugin kubernetes-cni pigz
Suggested packages:
  cgroupfs-mount | cgroup-lite docker-model-plugin
The following NEW packages will be installed:
  containerd.io docker-buildx-plugin docker-ce docker-ce-cli
  docker-ce-rootless-extras docker-compose-plugin kubeadm kubectl kubelet
  kubernetes-cni pigz
0 upgraded, 11 newly installed, 0 to remove and 200 not upgraded.
Need to get 177 MB of archives.
After this operation, 675 MB of additional disk space will be used.
Get:1 https://download.docker.com/linux/ubuntu noble/stable amd64 containerd.io amd64 2.3.6-1~ubuntu.24.04~noble [23.2 MB]
Get:2 http://archive.ubuntu.com/ubuntu noble/universe amd64 pigz amd64 2.8-1 [65.6 kB]
Get:6 https://download.docker.com/linux/ubuntu noble/stable amd64 docker-ce-cli amd64 5:29.8.1-1~ubuntu.24.04~noble [17.6 MB]
Get:3 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  kubeadm 1.36.5-1.1 [12.6 MB]
Get:8 https://download.docker.com/linux/ubuntu noble/stable amd64 docker-ce amd64 5:29.8.1-1~ubuntu.24.04~noble [24.3 MB]
Get:4 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  kubectl 1.36.5-1.1 [11.8 MB]
Get:9 https://download.docker.com/linux/ubuntu noble/stable amd64 docker-buildx-plugin amd64 0.37.1-1~ubuntu.24.04~noble [17.3 MB]
Get:5 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  kubernetes-cni 1.9.1-1.1 [39.0 MB]
Get:10 https://download.docker.com/linux/ubuntu noble/stable amd64 docker-ce-rootless-extras amd64 5:29.8.2-1~ubuntu.24.04~noble [10.2 MB]
Get:11 https://download.docker.com/linux/ubuntu noble/stable amd64 docker-compose-plugin amd64 5.6.0-1~ubuntu.24.04~noble [8080 kB]
Get:7 https://prod-cdn.packages.k8s.io/repositories/isv:/kubernetes:/core:/stable:/v1.36/deb  kubelet 1.36.5-1.1 [13.4 MB]
Fetched 177 MB in 1s (130 MB/s)
Selecting previously unselected package containerd.io.
(Reading database ... 
(Reading database ... 5%
(Reading database ... 10%
(Reading database ... 15%
(Reading database ... 20%
(Reading database ... 25%
(Reading database ... 30%
(Reading database ... 35%
(Reading database ... 40%
(Reading database ... 45%
(Reading database ... 50%
(Reading database ... 55%
(Reading database ... 60%
(Reading database ... 65%
(Reading database ... 70%
(Reading database ... 75%
(Reading database ... 80%
(Reading database ... 85%
(Reading database ... 90%
(Reading database ... 95%
(Reading database ... 100%
(Reading database ... 74849 files and directories currently installed.)
Preparing to unpack .../00-containerd.io_2.3.6-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking containerd.io (2.3.6-1~ubuntu.24.04~noble) ...
Selecting previously unselected package docker-ce-cli.
Preparing to unpack .../01-docker-ce-cli_5%3a29.8.1-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking docker-ce-cli (5:29.8.1-1~ubuntu.24.04~noble) ...
Selecting previously unselected package docker-ce.
Preparing to unpack .../02-docker-ce_5%3a29.8.1-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking docker-ce (5:29.8.1-1~ubuntu.24.04~noble) ...
Selecting previously unselected package pigz.
Preparing to unpack .../03-pigz_2.8-1_amd64.deb ...
Unpacking pigz (2.8-1) ...
Selecting previously unselected package docker-buildx-plugin.
Preparing to unpack .../04-docker-buildx-plugin_0.37.1-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking docker-buildx-plugin (0.37.1-1~ubuntu.24.04~noble) ...
Selecting previously unselected package docker-ce-rootless-extras.
Preparing to unpack .../05-docker-ce-rootless-extras_5%3a29.8.2-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking docker-ce-rootless-extras (5:29.8.2-1~ubuntu.24.04~noble) ...
Selecting previously unselected package docker-compose-plugin.
Preparing to unpack .../06-docker-compose-plugin_5.6.0-1~ubuntu.24.04~noble_amd64.deb ...
Unpacking docker-compose-plugin (5.6.0-1~ubuntu.24.04~noble) ...
Selecting previously unselected package kubeadm.
Preparing to unpack .../07-kubeadm_1.36.5-1.1_amd64.deb ...
Unpacking kubeadm (1.36.5-1.1) ...
Selecting previously unselected package kubectl.
Preparing to unpack .../08-kubectl_1.36.5-1.1_amd64.deb ...
Unpacking kubectl (1.36.5-1.1) ...
Selecting previously unselected package kubernetes-cni.
Preparing to unpack .../09-kubernetes-cni_1.9.1-1.1_amd64.deb ...
Unpacking kubernetes-cni (1.9.1-1.1) ...
Selecting previously unselected package kubelet.
Preparing to unpack .../10-kubelet_1.36.5-1.1_amd64.deb ...
Unpacking kubelet (1.36.5-1.1) ...
Setting up kubeadm (1.36.5-1.1) ...
Setting up docker-buildx-plugin (0.37.1-1~ubuntu.24.04~noble) ...
Setting up kubectl (1.36.5-1.1) ...
Setting up containerd.io (2.3.6-1~ubuntu.24.04~noble) ...
Created symlink /etc/systemd/system/multi-user.target.wants/containerd.service → /usr/lib/systemd/system/containerd.service.

Setting up docker-compose-plugin (5.6.0-1~ubuntu.24.04~noble) ...
Setting up docker-ce-cli (5:29.8.1-1~ubuntu.24.04~noble) ...
Setting up pigz (2.8-1) ...
Setting up docker-ce-rootless-extras (5:29.8.2-1~ubuntu.24.04~noble) ...
Setting up kubernetes-cni (1.9.1-1.1) ...
Setting up docker-ce (5:29.8.1-1~ubuntu.24.04~noble) ...
Created symlink /etc/systemd/system/multi-user.target.wants/docker.service → /usr/lib/systemd/system/docker.service.

Created symlink /etc/systemd/system/sockets.target.wants/docker.socket → /usr/lib/systemd/system/docker.socket.

Setting up kubelet (1.36.5-1.1) ...
Processing triggers for man-db (2.12.0-4build2) ...

Running kernel seems to be up-to-date.

No services need to be restarted.

No containers need to be restarted.

No user sessions are running outdated binaries.

No VM guests are running outdated hypervisor (qemu) binaries on this host.
containerd.io set on hold.
docker-ce set on hold.
docker-ce-cli set on hold.
docker-buildx-plugin set on hold.
kubelet set on hold.
kubeadm set on hold.
kubectl set on hold.
Synchronizing state of docker.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable docker
[init] Using Kubernetes version: v1.36.5
[preflight] Running pre-flight checks
[preflight] Pulling images required for setting up a Kubernetes cluster
[preflight] This might take a minute or two, depending on the speed of your internet connection
[preflight] You can also perform this action beforehand using 'kubeadm config images pull'
[certs] Using certificateDir folder "/etc/kubernetes/pki"
[certs] Generating "ca" certificate and key
[certs] Generating "apiserver" certificate and key
[certs] apiserver serving cert is signed for DNS names [kubernetes kubernetes.default kubernetes.default.svc kubernetes.default.svc.cluster.local vm-928254] and IPs [[redacted-ip] [redacted-ip]]
[certs] Generating "apiserver-kubelet-client" certificate and key
[certs] Generating "front-proxy-ca" certificate and key
[certs] Generating "front-proxy-client" certificate and key
[certs] Generating "etcd/ca" certificate and key
[certs] Generating "etcd/server" certificate and key
[certs] etcd/server serving cert is signed for DNS names [localhost vm-928254] and IPs [[redacted-ip] [redacted-ip] ::1]
[certs] Generating "etcd/peer" certificate and key
[certs] etcd/peer serving cert is signed for DNS names [localhost vm-928254] and IPs [[redacted-ip] [redacted-ip] ::1]
[certs] Generating "etcd/healthcheck-client" certificate and key
[certs] Generating "apiserver-etcd-client" certificate and key
[certs] Generating "sa" key and public key
[kubeconfig] Using kubeconfig folder "/etc/kubernetes"
[kubeconfig] Writing "admin.conf" kubeconfig file
[kubeconfig] Writing "super-admin.conf" kubeconfig file
[kubeconfig] Writing "kubelet.conf" kubeconfig file
[kubeconfig] Writing "controller-manager.conf" kubeconfig file
[kubeconfig] Writing "scheduler.conf" kubeconfig file
[etcd] Creating static Pod manifest for local etcd in "/etc/kubernetes/manifests"
[control-plane] Using manifest folder "/etc/kubernetes/manifests"
[control-plane] Creating static Pod manifest for "kube-apiserver"
[control-plane] Creating static Pod manifest for "kube-controller-manager"
[control-plane] Creating static Pod manifest for "kube-scheduler"
[kubelet-start] Writing kubelet environment file with flags to file "/var/lib/kubelet/kubeadm-flags.env"
[kubelet-start] Writing kubelet configuration to file "/var/lib/kubelet/instance-config.yaml"
[patches] Applied patch of type "application/strategic-merge-patch+json" to target "kubeletconfiguration"
[kubelet-start] Writing kubelet configuration to file "/var/lib/kubelet/config.yaml"
[kubelet-start] Starting the kubelet
[wait-control-plane] Waiting for the kubelet to boot up the control plane as static Pods from directory "/etc/kubernetes/manifests"
[kubelet-check] Waiting for a healthy kubelet at http://[redacted-ip]:10248/healthz. This can take up to 4m0s
[kubelet-check] The kubelet is healthy after 666.947µs
[control-plane-check] Waiting for healthy control plane components. This can take up to 4m0s
[control-plane-check] Checking kube-apiserver at https://[redacted-ip]:6443/livez
[control-plane-check] Checking kube-controller-manager at https://[redacted-ip]:10257/healthz
[control-plane-check] Checking kube-scheduler at https://[redacted-ip]:10259/livez
[control-plane-check] kube-scheduler is healthy after 3.651617ms
[control-plane-check] kube-controller-manager is healthy after 3.837602ms
[control-plane-check] kube-apiserver is healthy after 1.502106166s
[upload-config] Storing the configuration used in ConfigMap "kubeadm-config" in the "kube-system" Namespace
[kubelet] Creating a ConfigMap "kubelet-config" in namespace kube-system with the configuration for the kubelets in the cluster
[upload-certs] Skipping phase. Please see --upload-certs
[mark-control-plane] Marking the node vm-928254 as control-plane by adding the labels: [node-role.kubernetes.io/control-plane node.kubernetes.io/exclude-from-external-load-balancers]
[mark-control-plane] Marking the node vm-928254 as control-plane by adding the taints [node-role.kubernetes.io/control-plane:NoSchedule]
[bootstrap-token] Using token: [redacted-token]
[bootstrap-token] Configuring bootstrap tokens, cluster-info ConfigMap, RBAC Roles
[bootstrap-token] Configured RBAC rules to allow Node Bootstrap tokens to get nodes
[bootstrap-token] Configured RBAC rules to allow Node Bootstrap tokens to post CSRs in order for nodes to get long term certificate credentials
[bootstrap-token] Configured RBAC rules to allow the csrapprover controller automatically approve CSRs from a Node Bootstrap Token
[bootstrap-token] Configured RBAC rules to allow certificate rotation for all node client certificates in the cluster
[bootstrap-token] Configured RBAC rules to allow the API server kubelet client certificate to access the kubelet API
[bootstrap-token] Creating the "cluster-info" ConfigMap in the "kube-public" namespace
[kubelet-finalize] Updating "/etc/kubernetes/kubelet.conf" to point to a rotatable kubelet client certificate and key
[addons] Applied essential addon: CoreDNS
[addons] Applied essential addon: kube-proxy

Your Kubernetes control-plane has initialized successfully!

To start using your cluster, you need to run the following as a regular user:

  mkdir -p $HOME/.kube
  sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
  sudo chown $(id -u):$(id -g) $HOME/.kube/config

Alternatively, if you are the root user, you can run:

  export KUBECONFIG=/etc/kubernetes/admin.conf

You should now deploy a pod network to the cluster.
Run "kubectl apply -f [podnetwork].yaml" with one of the options listed at:
  https://kubernetes.io/docs/concepts/cluster-administration/addons/

Then you can join any number of worker nodes by running the following on each as root:

kubeadm join [redacted-ip]:6443 --token [redacted-token] \
	--discovery-token-ca-cert-hash [redacted-discovery-hash] 
node/vm-928254 untainted
namespace/kube-flannel created
serviceaccount/flannel created
clusterrole.rbac.authorization.k8s.io/flannel created
clusterrolebinding.rbac.authorization.k8s.io/flannel created
configmap/kube-flannel-cfg created
daemonset.apps/kube-flannel-ds created
node/vm-928254 condition met
deployment.apps/coredns condition met
Bootstrap ready: Ubuntu 24.04, amd64, Kubernetes 1.36.5, containerd 2.3.6-1~ubuntu.24.04~noble, Flannel 0.28.9, Helm 3.22.0.

```
