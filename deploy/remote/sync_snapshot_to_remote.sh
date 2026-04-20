#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 5 ]; then
  echo "Usage: $0 <snapshot_dir> <remote_host> <remote_port> <remote_user> <remote_project_dir> [ssh_key]"
  exit 1
fi

SNAPSHOT_DIR="$1"
REMOTE_HOST="$2"
REMOTE_PORT="$3"
REMOTE_USER="$4"
REMOTE_PROJECT_DIR="$5"
SSH_KEY="${6:-${SSH_KEY:-}}"

if [ ! -d "$SNAPSHOT_DIR" ]; then
  echo "Snapshot directory not found: $SNAPSHOT_DIR"
  exit 1
fi

SSH_OPTS=(-p "$REMOTE_PORT" -o StrictHostKeyChecking=no)
SCP_OPTS=(-P "$REMOTE_PORT" -o StrictHostKeyChecking=no)

if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
  SCP_OPTS+=(-i "$SSH_KEY")
fi

ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_PROJECT_DIR}/data/import_snapshot'"
scp "${SCP_OPTS[@]}" "$SNAPSHOT_DIR"/* "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PROJECT_DIR}/data/import_snapshot/"

echo "Snapshot copied to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PROJECT_DIR}/data/import_snapshot/"
echo "Next step: place the files into the final per-agent data paths and start the remote services."
