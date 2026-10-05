#!/usr/bin/env bash
set -euo pipefail

kubectl wait --for=condition=Available deployment/cloud-ops-demo-app -n cloud-ops --timeout=180s
kubectl wait --for=condition=Available deployment/cloud-ops-anomaly-detector -n cloud-ops --timeout=180s
kubectl get pods -n cloud-ops

kubectl run cloud-ops-smoke-test \
  --namespace cloud-ops \
  --image=curlimages/curl:8.11.1 \
  --restart=Never \
  --rm -i \
  --command -- curl --fail --silent http://cloud-ops-demo-app:8080/healthz

echo
echo "Application smoke test passed."
echo "Grafana: kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
echo "Prometheus: kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090"

