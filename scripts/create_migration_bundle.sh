#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_PATH="${1:-/tmp/openclaw_migration_${STAMP}.tar.gz}"
MANIFEST_PATH="/tmp/openclaw_migration_manifest_${STAMP}.txt"

cd "$ROOT_DIR"

FILES=()

add_if_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    FILES+=("$path")
  fi
}

add_if_exists ".env"
add_if_exists ".env.example"
add_if_exists "agent.db"
add_if_exists "control.json"
add_if_exists "bulk_copy_state.json"
add_if_exists "telethon_session.session"
add_if_exists "PROJECT_MEMORY.md"
add_if_exists "DEPLOY.md"
add_if_exists "WEBSITE_PUBLISH_API.md"
add_if_exists "deploy"
add_if_exists "config"
add_if_exists "data"

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No migration files found in $ROOT_DIR" >&2
  exit 1
fi

{
  echo "OpenClaw migration bundle"
  echo "Created at (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Project root: $ROOT_DIR"
  echo "Included files:"
  for file in "${FILES[@]}"; do
    echo "  - $file"
  done
} > "$MANIFEST_PATH"

tar -czf "$OUT_PATH" -C "$ROOT_DIR" "${FILES[@]}"

echo "Bundle created: $OUT_PATH"
echo "Manifest: $MANIFEST_PATH"
