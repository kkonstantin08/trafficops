#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$ROOT_DIR/deploy/versions.env"
readonly KUBECONFORM_VERSION=0.7.0
readonly KUBECONFORM_COMMIT=e65429b1e5990dd019ebb7b5642dcd22a3e9cd13
readonly KUBERNETES_SCHEMA_COMMIT=8df8a883b68a24a104b4a9e43c1288090ae60b3b
readonly GATEWAY_API_VERSION=1.4.1
readonly GATEWAY_API_SHA256=73b91b77f6be023a8c92c969fc664e5bd3b1a28aea59eac9ebc904607354dad2
readonly ENVOY_GATEWAY_COMMIT=0260554fd4f33b787aad77a129fc0ffeb00c1f29
readonly ENVOY_CRD_SHA256=3e9ea2f348445e3798b02daf02bf024b0d944227cf5ef8a18da7f675a1afd223
readonly ENVOY_BTP_CRD_SHA256=cd75a4c222df5487aa9ca8957b48bcc3255eb25de02ed9153faf620bc160f786
readonly PYYAML_VERSION=6.0.3
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
check_sha256() {
  local expected=$1 path=$2 actual
  actual=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$path")
  [[ $actual == "$expected" ]] || { printf 'SHA-256 mismatch: %s\n' "$path" >&2; exit 1; }
}

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64) platform=linux; arch=amd64; checksum=c31518ddd122663b3f3aa874cfe8178cb0988de944f29c74a0b9260920d115d3 ;;
  Linux/aarch64|Linux/arm64) platform=linux; arch=arm64; checksum=cc907ccf9e3c34523f0f32b69745265e0a6908ca85b92f41931d4537860eb83c ;;
  Darwin/x86_64) platform=darwin; arch=amd64; checksum=c6771cc894d82e1b12f35ee797dcda1f7da6a3787aa30902a15c264056dd40d4 ;;
  Darwin/arm64) platform=darwin; arch=arm64; checksum=b5d32b2cb77f9c781c976b20a85e2d0bc8f9184d5d1cfe665a2f31a19f99eeb9 ;;
  *) printf 'Unsupported platform: %s/%s\n' "$(uname -s)" "$(uname -m)" >&2; exit 2 ;;
esac

asset="kubeconform-${platform}-${arch}.tar.gz"
curl --fail --location --silent --show-error --max-time 60 \
  "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/${asset}" \
  -o "$tmp_dir/$asset"
check_sha256 "$checksum" "$tmp_dir/$asset"
tar -xzf "$tmp_dir/$asset" -C "$tmp_dir" kubeconform

curl --fail --location --silent --show-error --max-time 60 \
  "https://github.com/kubernetes-sigs/gateway-api/releases/download/v${GATEWAY_API_VERSION}/standard-install.yaml" \
  -o "$tmp_dir/gateway-api-crds.yaml"
curl --fail --location --silent --show-error --max-time 60 \
  "https://raw.githubusercontent.com/envoyproxy/gateway/${ENVOY_GATEWAY_COMMIT}/charts/gateway-helm/charts/crds/crds/generated/gateway.envoyproxy.io_envoyproxies.yaml" \
  -o "$tmp_dir/envoyproxy-crd.yaml"
curl --fail --location --silent --show-error --max-time 60 \
  "https://raw.githubusercontent.com/envoyproxy/gateway/${ENVOY_GATEWAY_COMMIT}/charts/gateway-helm/charts/crds/crds/generated/gateway.envoyproxy.io_backendtrafficpolicies.yaml" \
  -o "$tmp_dir/backendtrafficpolicy-crd.yaml"
check_sha256 "$GATEWAY_API_SHA256" "$tmp_dir/gateway-api-crds.yaml"
check_sha256 "$ENVOY_CRD_SHA256" "$tmp_dir/envoyproxy-crd.yaml"
check_sha256 "$ENVOY_BTP_CRD_SHA256" "$tmp_dir/backendtrafficpolicy-crd.yaml"

python3 -m venv "$tmp_dir/venv"
PIP_DEFAULT_TIMEOUT=15 PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$tmp_dir/venv/bin/python" -m pip install --only-binary=:all: --quiet "PyYAML==$PYYAML_VERSION"
curl --fail --location --silent --show-error --max-time 30 \
  "https://raw.githubusercontent.com/yannh/kubeconform/${KUBECONFORM_COMMIT}/scripts/openapi2jsonschema.py" \
  -o "$tmp_dir/openapi2jsonschema.py"
mkdir "$tmp_dir/schemas"
(
  cd "$tmp_dir/schemas"
  FILENAME_FORMAT='{kind}_{version}' "$tmp_dir/venv/bin/python" \
    "$tmp_dir/openapi2jsonschema.py" "$tmp_dir/gateway-api-crds.yaml" "$tmp_dir/envoyproxy-crd.yaml" \
    "$tmp_dir/backendtrafficpolicy-crd.yaml"
)
for schema in GatewayClass_v1 Gateway_v1 HTTPRoute_v1 EnvoyProxy_v1alpha1; do
  case "$schema" in
    GatewayClass_v1) source_schema=gatewayclass_v1 ;;
    Gateway_v1) source_schema=gateway_v1 ;;
    HTTPRoute_v1) source_schema=httproute_v1 ;;
    EnvoyProxy_v1alpha1) source_schema=envoyproxy_v1alpha1 ;;
    *) continue ;;
  esac
  [[ -e "$tmp_dir/schemas/$schema.json" ]] || ln -s "$source_schema.json" "$tmp_dir/schemas/$schema.json"
done
[[ -e "$tmp_dir/schemas/BackendTrafficPolicy_v1alpha1.json" ]] || \
  ln -s backendtrafficpolicy_v1alpha1.json "$tmp_dir/schemas/BackendTrafficPolicy_v1alpha1.json"

mkdir "$tmp_dir/kubernetes-schemas"
"$tmp_dir/venv/bin/python" - "$ROOT_DIR/deploy" "$tmp_dir/gvks.tsv" <<'PY'
import pathlib
import sys
import yaml

deploy_dir, output_path = map(pathlib.Path, sys.argv[1:])
gvks = set()
for manifest in sorted(deploy_dir.glob("*.yaml")):
    for resource in yaml.safe_load_all(manifest.read_text()):
        if not isinstance(resource, dict):
            continue
        api_group, api_version = (
            resource["apiVersion"].rsplit("/", 1)
            if "/" in resource["apiVersion"]
            else ("", resource["apiVersion"])
        )
        if api_group in {"gateway.networking.k8s.io", "gateway.envoyproxy.io"}:
            continue
        group_suffix = f"-{api_group.split('.')[0]}" if api_group else ""
        schema_name = f"{resource['kind'].lower()}{group_suffix}-{api_version}"
        kind_suffix = f"{group_suffix}-{api_version}"
        gvks.add((resource["kind"], schema_name, kind_suffix))

output_path.write_text("".join(f"{kind}\t{name}\t{suffix}\n" for kind, name, suffix in sorted(gvks)))
PY
while IFS=$'\t' read -r kind schema_name kind_suffix; do
  curl --fail --location --silent --show-error --max-time 30 \
    "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/${KUBERNETES_SCHEMA_COMMIT}/v${KUBERNETES_VERSION}-standalone-strict/${schema_name}.json" \
    -o "$tmp_dir/kubernetes-schemas/${schema_name}.json"
  [[ -e "$tmp_dir/kubernetes-schemas/${kind}${kind_suffix}.json" ]] ||
    ln -s "${schema_name}.json" "$tmp_dir/kubernetes-schemas/${kind}${kind_suffix}.json"
done <"$tmp_dir/gvks.tsv"

"$tmp_dir/kubeconform" -strict -summary -kubernetes-version "$KUBERNETES_VERSION" \
  -schema-location "$tmp_dir/schemas/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json" \
  -schema-location "$tmp_dir/kubernetes-schemas/{{.ResourceKind}}{{.KindSuffix}}.json" \
  "$ROOT_DIR"/deploy/*.yaml
