#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 /path/to/openclaw_migration.tar.gz /target/project/path" >&2
  exit 1
fi

BUNDLE_PATH="$1"
TARGET_DIR="$2"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${TARGET_DIR}/backup_before_restore_${STAMP}"

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "Bundle not found: $BUNDLE_PATH" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local path="$1"
  if [ -e "${TARGET_DIR}/${path}" ]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "$path")"
    cp -a "${TARGET_DIR}/${path}" "${BACKUP_DIR}/${path}"
  fi
}

backup_if_exists ".env"
backup_if_exists "agent.db"
backup_if_exists "control.json"
backup_if_exists "bulk_copy_state.json"
backup_if_exists "telethon_session.session"
backup_if_exists "config"
backup_if_exists "data"

tar -xzf "$BUNDLE_PATH" -C "$TARGET_DIR"

echo "Bundle restored into: $TARGET_DIR"
echo "Backup created at: $BACKUP_DIR"
