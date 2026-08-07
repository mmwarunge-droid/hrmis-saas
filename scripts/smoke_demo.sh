#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:5000}"
SMOKE_EMAIL="${DEMO_SMOKE_EMAIL:-employee@kinetic.demo}"
SMOKE_PASSWORD="${DEMO_SMOKE_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
LOGIN_BODY="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$LOGIN_BODY"' EXIT

if [[ -z "$SMOKE_PASSWORD" ]]; then
  echo "DEMO_SMOKE_PASSWORD is required" >&2
  exit 2
fi

assert_status() {
  local expected="$1"
  local url="$2"
  shift 2
  local status
  status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$@" "$url")"
  if [[ "$status" != "$expected" ]]; then
    echo "Smoke check failed: $url returned $status, expected $expected" >&2
    exit 1
  fi
  echo "OK $status $url"
}

assert_status 200 "$API_BASE_URL/health"
assert_status 200 "$API_BASE_URL/ready"

python3 - "$SMOKE_EMAIL" "$SMOKE_PASSWORD" "$LOGIN_BODY" <<'PY'
import json
import sys
from pathlib import Path

email, password, destination = sys.argv[1:]
Path(destination).write_text(json.dumps({
    'email': email,
    'password': password,
}))
PY

login_status="$(curl --silent --show-error \
  --cookie-jar "$COOKIE_JAR" \
  --output /tmp/kinetic-smoke-login.json \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --data-binary "@$LOGIN_BODY" \
  "$API_BASE_URL/api/auth/login")"

if [[ "$login_status" != "200" ]]; then
  echo "Smoke login failed with HTTP $login_status" >&2
  rm -f /tmp/kinetic-smoke-login.json
  exit 1
fi
rm -f /tmp/kinetic-smoke-login.json

echo "OK 200 demo login"
assert_status 200 "$API_BASE_URL/api/auth/me" --cookie "$COOKIE_JAR"
assert_status 200 "$API_BASE_URL/api/goals/summary" --cookie "$COOKIE_JAR"

echo "Kinetic deployment smoke checks passed."
