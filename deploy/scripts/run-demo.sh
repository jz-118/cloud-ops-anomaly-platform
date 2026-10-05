#!/usr/bin/env bash
set -euo pipefail

DURATION_SECONDS="${DURATION_SECONDS:-360}"
NORMAL_DELAY="${NORMAL_DELAY:-0.2}"

echo "Generating a normal baseline for ${DURATION_SECONDS} seconds."
kubectl run demo-normal-load -n cloud-ops --rm -i --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  "end=\$(\$(date +%s)+${DURATION_SECONDS}); while [ \$(date +%s) -lt \$end ]; do curl -s -o /dev/null http://cloud-ops-demo-app:8080/work; sleep ${NORMAL_DELAY}; done"

echo "Injecting latency and errors for 6 minutes."
kubectl run demo-fault-load -n cloud-ops --rm -i --restart=Never \
  --image=curlimages/curl:8.11.1 --command -- sh -c \
  'end=$(($(date +%s)+360)); while [ $(date +%s) -lt $end ]; do curl -s -o /dev/null "http://cloud-ops-demo-app:8080/work?latency_ms=1500&fail=true"; sleep 1; done'

