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

marker="verify-$(date +%s)"
url="http://${node_ip}:${node_port}/demo/region/east?request_id=${marker}&run_id=stage1"
last_status=''
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
    app_logs=$(kctl logs "deployment/demo-$response_version" -n trafficops --tail=100)
    grep -F '"event":"access"' <<<"$app_logs" | grep -Fq "\"request_id\":\"$marker\"" || {
      rm -f "$body"
      fail "request marker $marker was not found in the $response_version access log"
    }
    rm -f "$body"
    printf 'Gateway request and access log verified: HTTP %s, version %s, request_id %s\n' \
      "$last_status" "$response_version" "$marker"
    exit 0
  fi
  rm -f "$body"
  sleep 5
done
fail "Gateway request did not return HTTP 200 with JSON matching the current route weights within 60 seconds (last HTTP status: ${last_status:-no response})"
