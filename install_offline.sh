#!/usr/bin/env bash
# GitLane — installation offline (Linux/macOS / conda + pip)
# Usage: install_offline.sh [conda_env_name]
set -euo pipefail

ENV_NAME="${1:-gitlane}"
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backend"

echo "== GitLane offline install =="
echo "Env: $ENV_NAME"

if command -v conda >/dev/null 2>&1; then
  conda create -n "$ENV_NAME" python=3.13 -y
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "$ENV_NAME"
  if [ -d "$BACKEND_DIR/wheels" ]; then
    pip install --no-index --find-links="$BACKEND_DIR/wheels" -r "$BACKEND_DIR/requirements.txt"
  else
    pip install -r "$BACKEND_DIR/requirements.txt"
  fi
  echo
  echo "Lancement : conda activate $ENV_NAME && cd $BACKEND_DIR && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
else
  echo "conda not found - creating a plain venv instead."
  cd "$BACKEND_DIR"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  if [ -d "$BACKEND_DIR/wheels" ]; then
    pip install --no-index --find-links="$BACKEND_DIR/wheels" -r requirements.txt
  else
    pip install -r requirements.txt
  fi
  echo
  echo "Lancement : cd $BACKEND_DIR && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
fi