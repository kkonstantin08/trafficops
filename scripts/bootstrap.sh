#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
flannel_manifest=''
trap '[[ -z ${flannel_manifest:-} ]] || rm -f "$flannel_manifest"' EXIT
# versions.env is maintained in this repository and contains only fixed assignments.
# shellcheck disable=SC1091
source "$ROOT_DIR/deploy/versions.env"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
kctl() { kubectl --request-timeout=10s "$@"; }
need_root() { [[ $EUID -eq 0 ]] || fail 'run with sudo: sudo make bootstrap'; }
pkg_version() { dpkg-query -W -f='${Version}' "$1" 2>/dev/null || true; }
assert_pkg_version() {
  local name=$1 wanted=$2 installed
  installed=$(pkg_version "$name")
  [[ -z $installed || $installed == "$wanted" ]] || fail "$name $installed is installed; expected $wanted. Refusing to replace an existing runtime."
}

need_root
[[ -r /etc/os-release ]] || fail '/etc/os-release is missing'
# shellcheck disable=SC1091
source /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || fail 'requires Ubuntu 24.04'
[[ $(dpkg --print-architecture) == arm64 ]] || fail 'this build is pinned and verified for ARM64'
cpu_count=$(nproc)
memory_kib=$(awk '/MemTotal:/ { print $2 }' /proc/meminfo)
(( cpu_count >= 2 )) || fail 'Kubernetes single-node control plane needs at least 2 CPUs'
(( memory_kib >= 3 * 1024 * 1024 )) || fail 'minimum configured memory for this stage is 3 GiB; this does not establish capacity for later stages'
for host in pkgs.k8s.io download.docker.com github.com get.helm.sh registry-1.docker.io; do
  getent ahosts "$host" >/dev/null || fail "network/DNS preflight failed for $host"
done

if [[ -e /etc/kubernetes/admin.conf ]]; then
  [[ -f /var/lib/trafficops/bootstrap.env ]] || fail 'an unmanaged Kubernetes cluster already exists; refusing to modify it'
  command -v kubeadm >/dev/null || fail 'Kubernetes state exists but kubeadm is missing; refusing to reset or replace it'
  kubeadm version -o short | grep -Fx "v$KUBERNETES_VERSION" >/dev/null || fail 'an existing cluster uses a different kubeadm version; refusing to change it'
  KUBERNETES_ALREADY_INITIALIZED=1
elif [[ -e /etc/kubernetes/manifests/kube-apiserver.yaml ]]; then
  fail 'partial Kubernetes state found; inspect it manually before retrying'
else
  KUBERNETES_ALREADY_INITIALIZED=0
fi

if [[ $KUBERNETES_ALREADY_INITIALIZED == 0 ]]; then
  for port_proto in '6443 tcp' '10250 tcp' '30080 tcp' '8472 udp'; do
    read -r port proto <<<"$port_proto"
    proto_flag=t
    [[ $proto == udp ]] && proto_flag=u
    ss -H -l -"$proto_flag" "sport = :$port" | grep -q . && fail "required port $port/$proto is already in use"
  done
fi

for package_spec in \
  "containerd.io:$CONTAINERD_VERSION" \
  "docker-ce:$DOCKER_CE_VERSION" \
  "docker-ce-cli:$DOCKER_CE_VERSION" \
  "docker-buildx-plugin:$DOCKER_BUILDX_VERSION" \
  "kubelet:$KUBERNETES_PACKAGE_VERSION" \
  "kubeadm:$KUBERNETES_PACKAGE_VERSION" \
  "kubectl:$KUBERNETES_PACKAGE_VERSION"; do
  assert_pkg_version "${package_spec%%:*}" "${package_spec#*:}"
done

containerd_config=/etc/containerd/config.toml
containerd_config_preexisting=0
if [[ -e $containerd_config || -L $containerd_config ]]; then
  containerd_config_preexisting=1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gpg apt-transport-https python3
install -m 0755 -d /etc/apt/keyrings
curl --fail --location --silent --show-error --max-time 30 https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key |
  gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
chmod 0644 /etc/apt/keyrings/kubernetes-apt-keyring.gpg
cat >/etc/apt/sources.list.d/kubernetes.list <<'EOF'
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.36/deb/ /
EOF
curl --fail --location --silent --show-error --max-time 30 https://download.docker.com/linux/ubuntu/gpg |
  gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
chmod 0644 /etc/apt/keyrings/docker.gpg
printf 'deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu noble stable\n' \
  >/etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y \
  "containerd.io=$CONTAINERD_VERSION" \
  "docker-ce=$DOCKER_CE_VERSION" \
  "docker-ce-cli=$DOCKER_CE_VERSION" \
  "docker-buildx-plugin=$DOCKER_BUILDX_VERSION" \
  "kubelet=$KUBERNETES_PACKAGE_VERSION" \
  "kubeadm=$KUBERNETES_PACKAGE_VERSION" \
  "kubectl=$KUBERNETES_PACKAGE_VERSION"
apt-mark hold containerd.io docker-ce docker-ce-cli docker-buildx-plugin kubelet kubeadm kubectl

pause_image=$(kubeadm config images list --kubernetes-version "v$KUBERNETES_VERSION" | awk '/\/pause:/ { print; exit }')
[[ $pause_image =~ ^registry\.k8s\.io/pause:[0-9.]+$ ]] || fail 'could not resolve kubeadm pause image'
install -m 0755 -d /etc/containerd
if (( containerd_config_preexisting )); then
  python3 - "$containerd_config" "$pause_image" <<'PY'
import sys
import tomllib

path, expected_pause = sys.argv[1:]
try:
    with open(path, "rb") as config_file:
        config = tomllib.load(config_file)
except (OSError, tomllib.TOMLDecodeError) as error:
    raise SystemExit(f"cannot validate existing {path}: {error}")

disabled = set(config.get("disabled_plugins", []))
cri_plugins = {
    "cri",
    "io.containerd.grpc.v1.cri",
    "io.containerd.cri.v1.runtime",
    "io.containerd.cri.v1.images",
}
if disabled & cri_plugins:
    raise SystemExit(f"existing {path} disables CRI: {sorted(disabled & cri_plugins)}")

plugins = config.get("plugins", {})
runtime = plugins.get("io.containerd.cri.v1.runtime", {})
options = (
    runtime.get("containerd", {})
    .get("runtimes", {})
    .get("runc", {})
    .get("options", {})
)
pause = (
    plugins.get("io.containerd.cri.v1.images", {})
    .get("pinned_images", {})
    .get("sandbox")
)
if config.get("version") != 3 or options.get("SystemdCgroup") is not True or pause != expected_pause:
    raise SystemExit(
        f"existing {path} must use containerd 2.x config v3, "
        f"SystemdCgroup=true, and pinned_images.sandbox={expected_pause}; "
        "bootstrap left it unchanged"
    )
PY
else
  package_config_backup=/etc/containerd/config.toml.trafficops-package-default.bak
  if [[ -e $containerd_config ]]; then
    [[ -e $package_config_backup ]] || cp -a "$containerd_config" "$package_config_backup"
  fi
  config_tmp=$(mktemp /etc/containerd/config.toml.trafficops.XXXXXX)
  cat >"$config_tmp" <<EOF
# Managed by TrafficOps bootstrap; containerd 2.x config schema.
version = 3
required_plugins = ["io.containerd.cri.v1.runtime", "io.containerd.cri.v1.images"]

[plugins."io.containerd.cri.v1.images".pinned_images]
sandbox = "$pause_image"

[plugins."io.containerd.cri.v1.runtime".containerd.runtimes.runc.options]
SystemdCgroup = true
EOF
  chmod 0644 "$config_tmp"
  chown root:root "$config_tmp"
  mv -f "$config_tmp" "$containerd_config"
fi
systemctl enable --now containerd
systemctl restart containerd
systemctl enable --now docker

install -m 0755 -d /usr/local/lib/trafficops-tmp
helm_archive="/tmp/helm-v${HELM_VERSION}-linux-arm64.tar.gz"
curl --fail --location --silent --show-error --max-time 60 \
  "https://get.helm.sh/helm-v${HELM_VERSION}-linux-arm64.tar.gz" -o "$helm_archive"
printf '%s  %s\n' "$HELM_ARM64_SHA256" "$helm_archive" | sha256sum --check --status || fail 'Helm download checksum mismatch'
tar -xzf "$helm_archive" -C /usr/local/lib/trafficops-tmp linux-arm64/helm
install -m 0755 /usr/local/lib/trafficops-tmp/linux-arm64/helm /usr/local/bin/helm
rm -rf /usr/local/lib/trafficops-tmp "$helm_archive"
flannel_manifest=$(mktemp)
curl --fail --location --silent --show-error --max-time 60 \
  "https://github.com/flannel-io/flannel/releases/download/v$FLANNEL_VERSION/kube-flannel.yml" \
  -o "$flannel_manifest"
grep -Fq "ghcr.io/flannel-io/flannel:v$FLANNEL_VERSION" "$flannel_manifest" ||
  fail 'Flannel manifest does not contain the pinned Flannel image'
grep -Fq "ghcr.io/flannel-io/flannel-cni-plugin:v$FLANNEL_CNI_VERSION" "$flannel_manifest" ||
  fail 'Flannel manifest does not contain the pinned CNI plugin image'

swapoff -a
if ! grep -Eq '^[[:space:]]*[^#].*[[:space:]]swap[[:space:]]' /etc/fstab; then
  :
else
  [[ -e /etc/fstab.trafficops.bak ]] || cp -a /etc/fstab /etc/fstab.trafficops.bak
  sed -i -E '/^[[:space:]]*[^#].*[[:space:]]swap[[:space:]]/s/^/# TrafficOps disabled Kubernetes-incompatible swap: /' /etc/fstab
fi
modprobe overlay
modprobe br_netfilter
cat >/etc/modules-load.d/trafficops.conf <<'EOF'
overlay
br_netfilter
EOF
cat >/etc/sysctl.d/99-trafficops-kubernetes.conf <<'EOF'
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
sysctl --system >/dev/null
systemctl restart containerd
systemctl enable kubelet

if [[ $KUBERNETES_ALREADY_INITIALIZED == 0 ]]; then
  install -d -m 0755 /var/lib/trafficops
  cat >/var/lib/trafficops/bootstrap.env <<EOF
KUBERNETES_VERSION=$KUBERNETES_VERSION
FLANNEL_VERSION=$FLANNEL_VERSION
EOF
  kubeadm init --kubernetes-version "v$KUBERNETES_VERSION" --pod-network-cidr=10.244.0.0/16 --cri-socket=unix:///run/containerd/containerd.sock
  user=${SUDO_USER:-root}
  user_home=$(getent passwd "$user" | cut -d: -f6)
  [[ -n $user_home ]] || fail "could not resolve home directory for $user"
  install -d -m 0700 -o "$user" -g "$(id -gn "$user")" "$user_home/.kube"
  install -m 0600 -o "$user" -g "$(id -gn "$user")" /etc/kubernetes/admin.conf "$user_home/.kube/trafficops.conf"
fi

if [[ $KUBERNETES_ALREADY_INITIALIZED == 1 ]]; then
  kctl --kubeconfig=/etc/kubernetes/admin.conf get nodes --no-headers | grep -q . || fail 'existing cluster API is unreachable; refusing to modify it'
fi
node_count=$(kctl --kubeconfig=/etc/kubernetes/admin.conf get nodes --no-headers | wc -l | tr -d ' ')
[[ $node_count == 1 ]] || fail "expected one managed node; found $node_count"
kctl --kubeconfig=/etc/kubernetes/admin.conf taint nodes --all node-role.kubernetes.io/control-plane- --ignore-not-found=true
if kctl --kubeconfig=/etc/kubernetes/admin.conf get ds kube-flannel-ds -n kube-flannel >/dev/null 2>&1; then
  echo 'Flannel already exists; leaving its current state unchanged.'
else
  kctl --kubeconfig=/etc/kubernetes/admin.conf apply -f "$flannel_manifest"
fi
kubectl --kubeconfig=/etc/kubernetes/admin.conf wait --for=condition=Ready nodes --all --timeout=180s
kubectl --kubeconfig=/etc/kubernetes/admin.conf wait --for=condition=Available deployment/coredns -n kube-system --timeout=180s
printf 'Bootstrap ready: Ubuntu %s, arm64, Kubernetes %s, containerd %s, Flannel %s, Helm %s.\n' \
  "$VERSION_ID" "$KUBERNETES_VERSION" "$CONTAINERD_VERSION" "$FLANNEL_VERSION" "$HELM_VERSION"
