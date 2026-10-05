#!/usr/bin/env bash
set -euo pipefail

required=(curl git docker kubectl helm)
missing=()
for command_name in "${required[@]}"; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    missing+=("${command_name}")
  fi
done

if ((${#missing[@]} > 0)); then
  echo "Missing required commands: ${missing[*]}" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is unavailable." >&2
  exit 1
fi

echo "Preflight checks passed."

