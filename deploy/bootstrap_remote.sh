#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/fg/openclaw_telegram_agent}"
APP_USER="${APP_USER:-fg}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
OPENCLAW_ENV_DIR="${OPENCLAW_ENV_DIR:-/etc/openclaw}"
REPO_URL="${REPO_URL:-https://github.com/galaxlabs/openclaw_telegram_agent.git}"

echo "[1/6] Preparing application directory: ${APP_DIR}"
mkdir -p "${APP_DIR}"
chown "${APP_USER}:${APP_USER}" "${APP_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  echo "[2/6] Cloning repository"
  sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
else
  echo "[2/6] Repository already exists, skipping clone"
fi

echo "[3/6] Creating Python virtual environment"
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[4/6] Creating runtime directories"
mkdir -p "${APP_DIR}/data" "${APP_DIR}/config" "${OPENCLAW_ENV_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}/data" "${APP_DIR}/config"

echo "[5/6] Installing systemd units"
cp "${APP_DIR}"/deploy/systemd/openclaw-*.service "${SYSTEMD_DIR}/"
cp "${APP_DIR}"/deploy/systemd/openclaw-*.timer "${SYSTEMD_DIR}/"
systemctl daemon-reload

echo "[6/6] Done"
echo
echo "Next steps:"
echo "1. Create one env file per agent in ${OPENCLAW_ENV_DIR}/<agent>.env"
echo "2. Start the services you want, for example:"
echo "   sudo systemctl enable --now openclaw-collector@agent-a.service"
echo "   sudo systemctl enable --now openclaw-control-bot@agent-a.service"
echo "   sudo systemctl enable --now openclaw-rss@agent-a.timer"
echo "   sudo systemctl enable --now openclaw-post@agent-a.timer"
echo
echo "This installer does not touch nginx, Frappe benches, Redis, Supervisor, or ERPNext services."
