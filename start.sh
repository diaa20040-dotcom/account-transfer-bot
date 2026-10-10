#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
# Skip pip on hosts that already installed deps in the image (saves RAM at boot).
if [[ "${SKIP_PIP_ON_START:-1}" == "1" ]]; then
  :
elif [[ -f requirements.txt ]]; then
  pip install -q -r requirements.txt
fi
export ENABLE_WEB_ADMIN="${ENABLE_WEB_ADMIN:-false}"
exec python3 main.py
