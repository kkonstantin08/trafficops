#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$ROOT_DIR/deploy/versions.env"
export KUBECONFIG=${KUBECONFIG:-"$HOME/.kube/trafficops.conf"}
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
kctl() { kubectl --request-timeout=10s "$@"; }
[[ -r $KUBECONFIG ]] || fail "kubeconfig not found: $KUBECONFIG (run make bootstrap first)"
for cmd in kubectl curl python3; do command -v "$cmd" >/dev/null || fail "$cmd is required"; done

kctl get nodes -o wide
kctl get gatewayclass trafficops
kctl get gateway,httproute -n trafficops
kubectl wait --for=condition=Accepted gatewayclass/trafficops --timeout=30s
kubectl wait --for=condition=Accepted gateway/trafficops -n trafficops --timeout=30s
kubectl wait --for=condition=Programmed gateway/trafficops -n trafficops --timeout=30s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}'=True \
  httproute/demo-route -n trafficops --timeout=30s
kubectl wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="ResolvedRefs")].status}'=True \
  httproute/demo-route -n trafficops --timeout=30s
allowed_versions=$(kctl get httproute/demo-route -n trafficops -o json | python3 -c '
import json, sys
route = json.load(sys.stdin)
refs = {ref["name"]: int(ref.get("weight", 1)) for ref in route["spec"]["rules"][0]["backendRefs"]}
v1, v2 = refs.get("demo-v1", 0), refs.get("demo-v2", 0)
if v1 == 100 and v2 == 0:
    print("v1")
elif v1 == 0 and v2 == 100:
    print("v2")
elif v1 > 0 and v2 > 0 and v1 + v2 == 100:
    print("v1 v2")
else:
    raise SystemExit(f"unexpected demo-route weights: v1={v1}, v2={v2}")
') || fail 'could not determine current demo-route weights'
read -r -a allowed_versions <<<"$allowed_versions"

node_ip=$(kctl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
[[ -n $node_ip ]] || fail 'Kubernetes node has no InternalIP'
service=$(kctl get services -n envoy-gateway-system \
  -l gateway.envoyproxy.io/owning-gateway-namespace=trafficops,gateway.envoyproxy.io/owning-gateway-name=trafficops \
  -o jsonpath='{.items[0].metadata.name}')
[[ -n $service ]] || fail 'Envoy proxy Service for Gateway trafficops was not created'
node_port=$(kctl get service "$service" -n envoy-gateway-system \
  -o jsonpath='{.spec.ports[?(@.port==80)].nodePort}')
[[ $node_port == 30080 ]] || fail "expected Envoy HTTP NodePort 30080, got ${node_port:-none}"

marker="verify-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
url="http://${node_ip}:${node_port}/demo/region/east?request_id=${marker}&run_id=stage1"
last_status=''
response_version=''
for attempt in $(seq 1 12); do
  body=$(mktemp)
  last_status=$(curl --silent --show-error --max-time 5 -o "$body" -w '%{http_code}' \
    -H 'Host: trafficops.local' "$url" 2>/dev/null || true)
  if [[ $last_status == 200 ]] && python3 - "$body" "$marker" "${allowed_versions[@]}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as body:
    actual = json.load(body)
assert actual.get("service") == "trafficops-demo"
assert actual.get("version") in sys.argv[3:]
assert actual.get("region") == "east"
assert actual.get("request_id") == sys.argv[2]
assert actual.get("run_id") == "stage1"
PY
  then
    response_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$body")
    rm -f "$body"
    break
  fi
  rm -f "$body"
  sleep 5
done
[[ -n $response_version ]] || fail "Gateway request did not return HTTP 200 with JSON matching current route weights within 60 seconds (last HTTP status: ${last_status:-no response})"
printf 'Gateway response verified: HTTP %s, version %s, request_id %s\n' \
  "$last_status" "$response_version" "$marker"

find_fluentd_marker() {
  local started=$SECONDS row
  while ((SECONDS - started < 30)); do
    row=$(timeout 3s kubectl --request-timeout=2s exec -n observability daemonset/fluentd -- \
      /bin/sh -c 'find /logs -maxdepth 1 -type f -name "trafficops.*.log" -mmin -2 -print0 | xargs -0 -r grep -hF -m1 -- "$1" 2>/dev/null | head -n 1' \
      sh "$marker" 2>/dev/null || true)
    if [[ -n $row ]] && printf '%s\n' "$row" | PYTHONPATH="$ROOT_DIR" python3 -c \
      'import sys; from scripts.find_log_marker import record_matches; sys.exit(0 if record_matches(sys.stdin.read(), sys.argv[1], sys.argv[2]) else 1)' \
      "$marker" "$response_version"; then
      printf 'Fluentd log verified within 30 seconds: request_id %s, version %s\n' \
        "$marker" "$response_version"
      return 0
    fi
    sleep 1
  done
  return 1
}
find_fluentd_marker || fail "request_id $marker version $response_version was not found in collected Fluentd logs within 30 seconds"

prom_forward_log=$(mktemp)
prometheus_payload=$(mktemp)
prometheus_timestamps=$(mktemp)
app_metric_payload=$(mktemp)
app_metric_timestamp=$(mktemp)
timeout 90s kubectl --request-timeout=10s port-forward -n observability \
  service/prometheus 19090:9090 --address=127.0.0.1 >"$prom_forward_log" 2>&1 &
prom_forward_pid=$!
cleanup_prometheus_forward() {
  kill "$prom_forward_pid" 2>/dev/null || true
  rm -f "$prom_forward_log" "$prometheus_payload" "$prometheus_timestamps" \
    "$app_metric_payload" "$app_metric_timestamp"
}
trap cleanup_prometheus_forward EXIT

query="trafficops_http_requests_total{version=\"$response_version\",status=\"200\"}"
request_timestamp_query="timestamp($query)"
prom_started=$SECONDS
prom_verified=false
while ((SECONDS - prom_started < 60)); do
  if curl --silent --show-error --max-time 3 \
    'http://127.0.0.1:19090/api/v1/query?query=up' -o "$prometheus_payload" 2>/dev/null \
    && curl --silent --show-error --max-time 3 --get \
      --data-urlencode 'query=timestamp(up)' 'http://127.0.0.1:19090/api/v1/query' \
      -o "$prometheus_timestamps" 2>/dev/null \
    && curl --silent --show-error --max-time 3 --get \
      --data-urlencode "query=$query" 'http://127.0.0.1:19090/api/v1/query' \
      -o "$app_metric_payload" 2>/dev/null \
    && curl --silent --show-error --max-time 3 --get \
      --data-urlencode "query=$request_timestamp_query" 'http://127.0.0.1:19090/api/v1/query' \
      -o "$app_metric_timestamp" 2>/dev/null \
    && python3 - "$prometheus_payload" "$prometheus_timestamps" "$app_metric_payload" \
      "$app_metric_timestamp" "$response_version" <<'PY' >/dev/null 2>&1
import json
import sys
import time

def results(path):
    payload = json.load(open(path, encoding="utf-8"))
    if payload.get("status") != "success":
        raise ValueError("Prometheus query failed")
    return payload["data"]["result"]

now = time.time()
up = results(sys.argv[1])
up_timestamps = results(sys.argv[2])
required = {
    "trafficops-demo-v1",
    "trafficops-demo-v2",
    "envoy-proxy",
    "node-exporter",
    "kube-state-metrics",
}
healthy = set()
for sample in up:
    if sample["value"][1] == "1":
        healthy.add(sample["metric"].get("job"))
fresh = {
    sample["metric"].get("job")
    for sample in up_timestamps
    if -5 <= now - float(sample["value"][1]) <= 30
}
if not required <= healthy or not required <= fresh:
    raise ValueError("Prometheus targets are missing, down, or stale")
app_samples = results(sys.argv[3])
if not any(
    sample["metric"].get("version") == sys.argv[5]
    and float(sample["value"][1]) > 0
    for sample in app_samples
):
    raise ValueError("fresh application request metric is missing")
app_timestamps = results(sys.argv[4])
if not any(
    sample["metric"].get("version") == sys.argv[5]
    and -5 <= now - float(sample["value"][1]) <= 30
    for sample in app_timestamps
):
    raise ValueError("application request metric is stale")
PY
  then
    prom_verified=true
    break
  fi
  sleep 2
done
[[ $prom_verified == true ]] || fail 'Prometheus did not expose fresh, healthy samples for both apps, Envoy, node-exporter, kube-state-metrics, and the verified request within 60 seconds'
printf 'Prometheus verified: fresh up samples for all five jobs and HTTP 200 counter for %s\n' "$response_version"
