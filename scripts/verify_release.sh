#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
ruff check .
pytest -q

cleanup() {
  rm -rf "$ROOT_DIR/frontend/dist"
}
trap cleanup EXIT

cd "$ROOT_DIR/frontend"
npm run lint
npm test
npm run build

# Generated bundles are not source files and should not be scanned by
# the source-branding verifier.
rm -rf "$ROOT_DIR/frontend/dist"

cd "$ROOT_DIR"
python scripts/verify_kinetic_branding.py
git diff --check

echo "Kinetic release verification passed."
