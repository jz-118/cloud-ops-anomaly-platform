#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace monitoring cloud-ops-alerting=enabled --overwrite
kubectl create namespace cloud-ops --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace cloud-ops cloud-ops-alerting=enabled --overwrite

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values "${ROOT_DIR}/deploy/monitoring/values.yaml" \
  --wait \
  --timeout 15m

echo "Monitoring stack is ready."

