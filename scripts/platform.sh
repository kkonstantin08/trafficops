#!/usr/bin/env bash

trafficops_select_platform() {
  case "$1" in
    arm64)
      PLATFORM_ARCH=arm64
      HELM_PLATFORM=linux-arm64
      HELM_SHA256=$HELM_ARM64_SHA256
      PROMETHEUS_IMAGE=$PROMETHEUS_IMAGE_ARM64
      FLUENTD_IMAGE=$FLUENTD_IMAGE_ARM64
      NODE_EXPORTER_IMAGE=$NODE_EXPORTER_IMAGE_ARM64
      KUBE_STATE_METRICS_IMAGE=$KUBE_STATE_METRICS_IMAGE_ARM64
      ;;
    amd64)
      PLATFORM_ARCH=amd64
      HELM_PLATFORM=linux-amd64
      HELM_SHA256=$HELM_AMD64_SHA256
      PROMETHEUS_IMAGE=$PROMETHEUS_IMAGE_AMD64
      FLUENTD_IMAGE=$FLUENTD_IMAGE_AMD64
      NODE_EXPORTER_IMAGE=$NODE_EXPORTER_IMAGE_AMD64
      KUBE_STATE_METRICS_IMAGE=$KUBE_STATE_METRICS_IMAGE_AMD64
      ;;
    *) printf 'ERROR: unsupported Debian architecture: %s (supported: arm64, amd64)\n' "$1" >&2; return 1 ;;
  esac
  for image in "$PROMETHEUS_IMAGE" "$FLUENTD_IMAGE" "$NODE_EXPORTER_IMAGE" "$KUBE_STATE_METRICS_IMAGE"; do
    [[ $image == *@sha256:* ]] || { printf 'ERROR: missing or invalid observability image pin for %s\n' "$PLATFORM_ARCH" >&2; return 1; }
  done
  [[ $HELM_SHA256 =~ ^[[:xdigit:]]{64}$ ]] || { printf 'ERROR: missing or invalid Helm SHA-256 for %s\n' "$PLATFORM_ARCH" >&2; return 1; }
}

trafficops_require_node_arch() {
  [[ $1 == "$2" ]] || {
    printf 'ERROR: host architecture %s does not match Kubernetes node architecture %s\n' "${1:-unknown}" "${2:-unknown}" >&2
    return 1
  }
}
