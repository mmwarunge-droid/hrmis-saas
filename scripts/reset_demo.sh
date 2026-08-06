#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFERENCE_DATE="${1:-${DEMO_REFERENCE_DATE:-$(date +%F)}}"

cd "$ROOT_DIR/backend"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

flask --app run.py db upgrade
flask --app run.py demo-reset --yes --as-of "$REFERENCE_DATE"
flask --app run.py demo-status --as-of "$REFERENCE_DATE"

echo "Kinetic demo reset completed for $REFERENCE_DATE"
