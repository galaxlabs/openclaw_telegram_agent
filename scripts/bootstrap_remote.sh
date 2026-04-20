#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/fg/openclaw_telegram_agent}"
REPO_URL="${REPO_URL:-https://github.com/galaxlabs/openclaw_telegram_agent.git}"
REPO_REF="${REPO_REF:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_SYSTEMD="${INSTALL_SYSTEMD:-0}"
ENABLE_AGENT="${ENABLE_AGENT:-}"

echo "[openclaw] bootstrap starting"
echo "APP_DIR=${APP_DIR}"
echo "REPO_URL=${REPO_URL}"
echo "REPO_REF=${REPO_REF}"

mkdir -p "$(dirname "${APP_DIR}")"

if [ ! -d "${APP_DIR}/.git" ]; then
  git clone "${REPO_URL}" "${APP_DIR}"
fi

git -C "${APP_DIR}" fetch --all --tags
git -C "${APP_DIR}" checkout "${REPO_REF}"

cd "${APP_DIR}"

if [ ! -d .venv ]; then
  "${PYTHON_BIN}" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir -p data config logs

if [ "${INSTALL_SYSTEMD}" = "1" ]; then
  sudo mkdir -p /etc/openclaw
  sudo cp deploy/systemd/openclaw-*.service /etc/systemd/system/
  sudo cp deploy/systemd/openclaw-*.timer /etc/systemd/system/
  sudo systemctl daemon-reload

  if [ -n "${ENABLE_AGENT}" ]; then
    sudo systemctl enable openclaw-collector@"${ENABLE_AGENT}".service
    sudo systemctl enable openclaw-control-bot@"${ENABLE_AGENT}".service
    sudo systemctl enable openclaw-rss@"${ENABLE_AGENT}".timer
    sudo systemctl enable openclaw-post@"${ENABLE_AGENT}".timer
  fi
fi

echo "[openclaw] bootstrap complete"
echo "Next:"
echo "1. Create /etc/openclaw/<agent>.env from deploy/examples/*.env.example"
echo "2. Decide whether this is staging or production"
echo "3. Only start the collector/timers after staged verification"
