#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/rl-sim ]]; then
  echo "Install the Python package first; see README.md."
  exit 1
fi
if [[ ! -f web/dist/index.html ]]; then
  echo "Build the studio first: cd web && npm install && npm run build"
  exit 1
fi
exec .venv/bin/rl-sim serve "$@"
