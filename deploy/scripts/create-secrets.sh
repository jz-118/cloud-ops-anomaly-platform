#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Create .env from .env.example before creating secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

required=(SMTP_SMARTHOST SMTP_FROM SMTP_TO SMTP_USERNAME SMTP_PASSWORD)
for variable in "${required[@]}"; do
  if [[ -z "${!variable:-}" || "${!variable}" == "replace-me" ]]; then
    echo "${variable} is missing or still uses the placeholder value." >&2
    exit 1
  fi
done

kubectl create namespace cloud-ops --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic cloud-ops-smtp \
  --namespace cloud-ops \
  --from-literal=password="${SMTP_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

sed \
  -e "s|REPLACE_SMTP_TO|${SMTP_TO}|g" \
  -e "s|REPLACE_SMTP_FROM|${SMTP_FROM}|g" \
  -e "s|REPLACE_SMTP_SMARTHOST|${SMTP_SMARTHOST}|g" \
  -e "s|REPLACE_SMTP_USERNAME|${SMTP_USERNAME}|g" \
  "${ROOT_DIR}/deploy/alertmanager/alertmanager-config.yaml" | kubectl apply -f -

echo "SMTP secret and Alertmanager routing have been applied."

