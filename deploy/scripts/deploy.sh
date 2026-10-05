#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${NAMESPACE:-cloud-ops}"
RELEASE="${RELEASE:-cloud-ops}"

docker build -t cloud-ops-demo:latest "${ROOT_DIR}/demo-app"
docker build -t cloud-ops-detector:latest "${ROOT_DIR}/anomaly-detector"

docker save cloud-ops-demo:latest | sudo k3s ctr images import -
docker save cloud-ops-detector:latest | sudo k3s ctr images import -

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install "${RELEASE}" "${ROOT_DIR}/deploy/helm/cloud-ops-platform" \
  --namespace "${NAMESPACE}" \
  --wait \
  --timeout 10m

kubectl apply -f "${ROOT_DIR}/deploy/grafana/dashboard-configmap.yaml"
echo "Cloud Ops platform is deployed."

