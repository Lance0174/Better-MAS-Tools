#!/usr/bin/env bash
set -euo pipefail

project_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_directory"
if [[ "${1:-}" == "--skip-install" ]]; then
  shift
else
  command -v uv >/dev/null || { echo 'Install uv first: https://docs.astral.sh/uv/'; exit 1; }
  command -v yarn >/dev/null || { echo 'Install Node.js 22 and enable Corepack first.'; exit 1; }
  uv sync --locked --extra captcha --no-dev
  (cd frontend && yarn install --immutable --mode=skip-build && yarn typecheck && yarn build)
fi
[[ -x .venv/bin/python && -f frontend/dist/index.html ]] || { echo 'Build the project first (run without --skip-install).'; exit 1; }
exec .venv/bin/python main.py "$@"
