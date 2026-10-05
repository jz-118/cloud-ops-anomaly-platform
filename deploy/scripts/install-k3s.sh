#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer must run on Linux." >&2
  exit 1
fi

if command -v k3s >/dev/null 2>&1; then
  echo "k3s is already installed."
else
  curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
fi

mkdir -p "${HOME}/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "${HOME}/.kube/config"
sudo chown "$(id -u):$(id -g)" "${HOME}/.kube/config"
export KUBECONFIG="${HOME}/.kube/config"
kubectl wait --for=condition=Ready node --all --timeout=180s
echo "k3s is ready."

