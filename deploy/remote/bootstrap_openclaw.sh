#!/usr/bin/env bash
set -euo pipefail

SERVICE_USER="${SERVICE_USER:-fg}"
HOME_DIR="${HOME_DIR:-/home/${SERVICE_USER}}"
REPO_URL="${REPO_URL:-https://github.com/galaxlabs/openclaw_telegram_agent.git}"
REPO_DIR="${REPO_DIR:-${HOME_DIR}/openclaw_telegram_agent}"
ENV_DIR="${ENV_DIR:-/etc/openclaw}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[openclaw] bootstrap started"
echo "  service user: ${SERVICE_USER}"
echo "  repo dir:     ${REPO_DIR}"
echo "  env dir:      ${ENV_DIR}"

if [[ "$(id -un)" != "${SERVICE_USER}" ]]; then
  echo "[openclaw] warning: current user is $(id -un), expected ${SERVICE_USER}"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[openclaw] git is required"
  exit 1
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[openclaw] ${PYTHON_BIN} is required"
  exit 1
fi

mkdir -p "${HOME_DIR}"

if [[ -d "${REPO_DIR}/.git" ]]; then
  echo "[openclaw] updating existing repo"
  git -C "${REPO_DIR}" fetch --all --tags
  git -C "${REPO_DIR}" pull --ff-only
else
  echo "[openclaw] cloning repo"
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

cd "${REPO_DIR}"

echo "[openclaw] preparing virtualenv"
if [[ ! -d .venv ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[openclaw] creating runtime directories"
mkdir -p data config logs

echo "[openclaw] validating Python files"
python -m py_compile runtime_support.py publish_support.py post_organized.py collector.py control_bot.py rss_collector.py

if command -v sudo >/dev/null 2>&1; then
  echo "[openclaw] installing systemd unit files"
  sudo mkdir -p "${ENV_DIR}"
  sudo cp deploy/systemd/openclaw-*.service /etc/systemd/system/
  sudo cp deploy/systemd/openclaw-*.timer /etc/systemd/system/
  sudo systemctl daemon-reload
else
  echo "[openclaw] sudo not found, skipping systemd install"
fi

echo
echo "[openclaw] bootstrap complete"
echo "Next steps:"
echo "  1. Create one env file per agent inside ${ENV_DIR}"
echo "  2. Add RSS feed list files under ${REPO_DIR}/config if needed"
echo "  3. Enable services, for example:"
echo "     sudo systemctl enable --now openclaw-collector@agent-a.service"
echo "     sudo systemctl enable --now openclaw-control-bot@agent-a.service"
echo "     sudo systemctl enable --now openclaw-rss@agent-a.timer"
echo "     sudo systemctl enable --now openclaw-post@agent-a.timer"
echo
echo "This script does not modify nginx, Frappe, ERPNext, or ports."
