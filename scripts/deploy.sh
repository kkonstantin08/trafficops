#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$ROOT_DIR/deploy/versions.env"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/platform.sh"
export KUBECONFIG=${KUBECONFIG:-"$HOME/.kube/trafficops.conf"}
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
kctl() { kubectl --request-timeout=10s "$@"; }
for cmd in kubectl helm docker ctr; do command -v "$cmd" >/dev/null || fail "$cmd is required; run make bootstrap first"; done
[[ -r $KUBECONFIG ]] || fail "kubeconfig not found: $KUBECONFIG (run make bootstrap first)"
kctl cluster-info >/dev/null || fail 'Kubernetes API is unavailable'
trafficops_select_platform "$(dpkg --print-architecture)" || fail 'unsupported host architecture or missing platform pins'
node_count=$(kctl get nodes --no-headers | wc -l | tr -d ' ')
[[ $node_count == 1 ]] || fail "local image import requires exactly one Kubernetes node; found $node_count"
node_platform=$(kctl get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}')
trafficops_require_node_arch "$PLATFORM_ARCH" "$node_platform" || fail 'local image import requires matching host and node architectures'

SUDO=()
[[ $EUID -eq 0 ]] || SUDO=(sudo)
printf 'Building %s from the repository Dockerfile...\n' "$DEMO_IMAGE"
"${SUDO[@]}" docker build --tag "$DEMO_IMAGE" --file "$ROOT_DIR/Dockerfile" "$ROOT_DIR"
"${SUDO[@]}" docker save "$DEMO_IMAGE" | "${SUDO[@]}" ctr --namespace k8s.io images import -

kctl create namespace trafficops --dry-run=client -o yaml | kctl apply -f -
if ! kctl get configmap/demo-v2-config -n trafficops >/dev/null 2>&1; then
  kctl create configmap demo-v2-config -n trafficops --from-literal=APP_FORCE_ERRORS=false
fi
kctl apply -f "$ROOT_DIR/deploy/base.yaml"
source_sha=$(cat "$ROOT_DIR/Dockerfile" "$ROOT_DIR/demo/app.py" "$ROOT_DIR/requirements.lock" | sha256sum | awk '{print $1}')
for deployment in demo-v1 demo-v2; do
  current_sha=$(kctl get "deployment/$deployment" -n trafficops \
    -o go-template='{{index .metadata.annotations "trafficops.io/source-sha256"}}' 2>/dev/null || true)
  if [[ -n $current_sha && $current_sha != "$source_sha" ]]; then
    kctl rollout restart "deployment/$deployment" -n trafficops
  fi
  kctl annotate "deployment/$deployment" -n trafficops \
    "trafficops.io/source-sha256=$source_sha" --overwrite
  kubectl --request-timeout=180s rollout status "deployment/$deployment" -n trafficops --timeout=180s
done

helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm \
  --version "v$ENVOY_GATEWAY_VERSION" \
  --namespace envoy-gateway-system --create-namespace \
  --wait --timeout=300s
kubectl wait --for=condition=Available deployment/envoy-gateway \
  -n envoy-gateway-system --timeout=180s
kctl apply -f "$ROOT_DIR/deploy/envoy-proxy.yaml"
kctl apply -f "$ROOT_DIR/deploy/gateway.yaml"
if ! kctl get httproute/demo-route -n trafficops -o name >/dev/null 2>&1; then
  kctl apply -f "$ROOT_DIR/deploy/route.yaml"
else
  echo 'HTTPRoute demo-route already exists; preserving its current traffic weights.'
fi
kubectl wait --for=condition=Accepted gatewayclass/trafficops --timeout=120s
kubectl wait --for=condition=Accepted gateway/trafficops -n trafficops --timeout=120s
kubectl wait --for=condition=Programmed gateway/trafficops -n trafficops --timeout=120s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}'=True \
  httproute/demo-route -n trafficops --timeout=120s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="ResolvedRefs")].status}'=True \
  httproute/demo-route -n trafficops --timeout=120s

obs_node=$(kctl get nodes -o jsonpath='{.items[0].metadata.name}')
[[ -n $obs_node ]] || fail 'Kubernetes node name is unavailable for local observability volumes'
kctl label node "$obs_node" trafficops.io/observability-node=true --overwrite
SUDO=()
[[ $EUID -eq 0 ]] || SUDO=(sudo)
"${SUDO[@]}" install -d -o 65534 -g 65534 -m 0750 /var/lib/trafficops/prometheus
"${SUDO[@]}" install -d -m 0755 /var/lib/trafficops/fluentd/logs /var/lib/trafficops/fluentd/buffer
"${SUDO[@]}" install -d -o 65532 -g 65532 -m 0750 /var/lib/trafficops/controller

observability_manifest=$(mktemp)
trap 'rm -f "$observability_manifest"' EXIT
sed \
  -e "s|__PROMETHEUS_IMAGE__|$PROMETHEUS_IMAGE|g" \
  -e "s|__FLUENTD_IMAGE__|$FLUENTD_IMAGE|g" \
  -e "s|__NODE_EXPORTER_IMAGE__|$NODE_EXPORTER_IMAGE|g" \
  -e "s|__KUBE_STATE_METRICS_IMAGE__|$KUBE_STATE_METRICS_IMAGE|g" \
  "$ROOT_DIR/deploy/observability.yaml" >"$observability_manifest"
kctl apply -f "$observability_manifest"

apply_config() {
  local name=$1 file=$2 workload=$3 hash current
  hash=$(sha256sum "$file" | awk '{print $1}')
  current=$(kctl get "$workload" -n observability \
    -o go-template='{{index .spec.template.metadata.annotations "trafficops.io/config-sha256"}}' 2>/dev/null || true)
  kctl create configmap "$name" -n observability --from-file="$file" \
    --dry-run=client -o yaml | kctl apply -f -
  if [[ $current != "$hash" ]]; then
    kctl patch "$workload" -n observability --type=merge \
      -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"trafficops.io/config-sha256\":\"$hash\"}}}}}"
  fi
}
apply_config prometheus-config "$ROOT_DIR/deploy/prometheus.yml" deployment/prometheus
apply_config fluentd-config "$ROOT_DIR/deploy/fluent.conf" daemonset/fluentd

kubectl --request-timeout=180s rollout status deployment/prometheus -n observability --timeout=180s
kubectl --request-timeout=180s rollout status deployment/kube-state-metrics -n observability --timeout=180s
kubectl --request-timeout=180s rollout status daemonset/node-exporter -n observability --timeout=180s
kubectl --request-timeout=180s rollout status daemonset/fluentd -n observability --timeout=180s

trafficops_config_dir=${XDG_CONFIG_HOME:-"$HOME/.config"}/trafficops
admin_password_file=$trafficops_config_dir/admin-password
admin_hash_file=$trafficops_config_dir/admin-password-hash
install -d -m 0700 "$trafficops_config_dir"
secret_exists=false
if kctl get secret/trafficops-controller -n trafficops >/dev/null 2>&1; then secret_exists=true; fi
if [[ ! -s $admin_password_file || ! -s $admin_hash_file ]]; then
  [[ $secret_exists == false ]] || fail "controller secret exists; retain the original password file at $admin_password_file"
  umask 077
  python3 - "$admin_password_file" "$admin_hash_file" <<'PY'
import hashlib
import secrets
import sys

password = secrets.token_urlsafe(32)
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000).hex()
open(sys.argv[1], "w", encoding="utf-8").write(password)
open(sys.argv[2], "w", encoding="utf-8").write(f"pbkdf2_sha256$310000${salt.hex()}${digest}")
PY
  chmod 0600 "$admin_password_file" "$admin_hash_file"
fi
if [[ $secret_exists == false ]]; then
  kctl create secret generic trafficops-controller -n trafficops \
    --from-file=admin-password-hash="$admin_hash_file"
  printf 'Controller password saved outside the repository: %s\n' "$admin_password_file"
fi

node_ip=$(kctl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
[[ -n $node_ip ]] || fail 'Kubernetes node InternalIP is unavailable for controller routing'
controller_source_sha=$(cat "$ROOT_DIR/Dockerfile" "$ROOT_DIR/controller/"*.py "$ROOT_DIR/web/"* \
  "$ROOT_DIR/deploy/controller.yaml" "$ROOT_DIR/deploy/controller-route.yaml" \
  "$ROOT_DIR/requirements.lock" | sha256sum | awk '{print $1}')
controller_manifest=$(mktemp)
sed \
  -e "s|__DEMO_IMAGE__|$DEMO_IMAGE|g" \
  -e "s|__NODE_IP__|$node_ip|g" \
  -e "s|__PUBLIC_ORIGIN__|http://$node_ip:30080|g" \
  -e "s|__CONTROLLER_SOURCE_SHA__|$controller_source_sha|g" \
  "$ROOT_DIR/deploy/controller.yaml" >"$controller_manifest"
kctl apply -f "$controller_manifest"
rm -f "$controller_manifest"
kctl apply -f "$ROOT_DIR/deploy/controller-route.yaml"
kubectl --request-timeout=180s rollout status deployment/trafficops-controller -n trafficops --timeout=180s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}'=True \
  httproute/trafficops-panel -n trafficops --timeout=60s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="ResolvedRefs")].status}'=True \
  httproute/trafficops-panel -n trafficops --timeout=60s

"$ROOT_DIR/scripts/verify.sh"
