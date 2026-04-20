# OpenClaw Telegram Agent Deployment

This repo now supports repeatable VPS installs and multiple named agent instances from one codebase.

## 1. Install the app on the VPS

```bash
cd /home/fg
git clone https://github.com/galaxlabs/openclaw_telegram_agent.git
cd openclaw_telegram_agent
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data config
```

Or use the bootstrap helper:

```bash
cd /home/fg/openclaw_telegram_agent
bash scripts/bootstrap_remote.sh
```

Or use the prepared bootstrap script after copying the repo to the VPS:

```bash
sudo bash /home/fg/openclaw_telegram_agent/deploy/bootstrap_remote.sh
```

Or use the bootstrap helper from this repo:

```bash
cd /home/fg/openclaw_telegram_agent
bash deploy/remote/bootstrap_openclaw.sh
```

## 2. Create one env file per agent

Create files like `/etc/openclaw/agent-a.env` and `/etc/openclaw/agent-b.env`.

Use `.env.example` as the template, but give every agent its own:

- `DB_PATH`
- `CONTROL_PATH`
- `TELETHON_SESSION_NAME`
- `BULK_STATE_FILE`
- source/target chat IDs
- optional `CONTROL_BOT_TOKEN`

Example:

```env
TELEGRAM_BOT_TOKEN=...
CONTROL_BOT_TOKEN=...
TELEGRAM_TARGET_CHAT_ID=-1001234567890
TELEGRAM_SOURCE_CHAT_IDS=-1001111111111,-1002222222222
DB_PATH=/home/fg/openclaw_telegram_agent/data/agent-a.db
CONTROL_PATH=/home/fg/openclaw_telegram_agent/data/control-agent-a.json
POST_LIMIT=5
RSS_FEEDS_FILE=/home/fg/openclaw_telegram_agent/config/rss_feeds_agent_a.txt
TELETHON_SESSION_NAME=/home/fg/openclaw_telegram_agent/data/telethon_agent_a
BULK_STATE_FILE=/home/fg/openclaw_telegram_agent/data/bulk_copy_agent_a.json
WEBSITE_PUBLISH_ENABLED=1
WEBSITE_PUBLISH_URL=https://your-site.vercel.app/api/openclaw/publish
WEBSITE_PUBLISH_TOKEN=...
```

For staged migration without breaking the live local instance, also see:

- `deploy/examples/agent-stage.env.example`
- `deploy/examples/agent-prod.env.example`
- `MIGRATION_CUTOVER.md`

## 2b. Choose the publish mode

The agent now supports three output modes:

- Telegram only
  Set `TELEGRAM_TARGET_CHAT_ID`.
  Leave `WEBSITE_PUBLISH_ENABLED=0`.

- Website only
  Set `WEBSITE_PUBLISH_ENABLED=1` and `WEBSITE_PUBLISH_URL`.
  `TELEGRAM_TARGET_CHAT_ID` can stay empty.

- Website + Telegram
  Set both Telegram and website env values.
  The item is only marked fully processed after the enabled steps succeed.

If `DELETE_SOURCE_AFTER_PUBLISH=1`, the agent deletes the original source Telegram message after the enabled publishing steps complete.

## 3. Install systemd units

```bash
sudo mkdir -p /etc/openclaw
sudo cp deploy/systemd/openclaw-*.service /etc/systemd/system/
sudo cp deploy/systemd/openclaw-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

## 4. Start one named instance

```bash
sudo systemctl enable --now openclaw-collector@agent-a.service
sudo systemctl enable --now openclaw-control-bot@agent-a.service
sudo systemctl enable --now openclaw-rss@agent-a.timer
sudo systemctl enable --now openclaw-post@agent-a.timer
```

## 5. Check logs

```bash
sudo journalctl -u openclaw-collector@agent-a.service -f
sudo journalctl -u openclaw-control-bot@agent-a.service -f
sudo journalctl -u openclaw-rss@agent-a.service -f
sudo journalctl -u openclaw-post@agent-a.service -f
```

## 6. SSH convenience

There is a ready example at `deploy/ssh_config.example`.
The current reachable SSH port is `4645`.
You can add it into your local `~/.ssh/config` and connect with:

```bash
ssh openclaw-vps
```

## 7. Network check when SSH still times out

Key auth does not fix a network timeout.
If `ssh -p 4645 fg@72.60.118.195` still times out, check on the VPS/provider side:

- `sshd` is running
- `sshd` is listening on port `4645`
- UFW or firewall allows `4645/tcp`
- cloud/provider firewall or NAT forwards `4645`
- the VPS public IP is really `72.60.118.195`

## Notes

- `collector.py` now auto-creates and auto-migrates the SQLite schema for fresh installs.
- `post_organized.py` now supports `POST_LIMIT` or `--limit`.
- Multiple agents are safe as long as each instance uses separate data file paths.
- `post_organized.py` can now publish to an external website endpoint such as a Vercel API route before marking items processed.
- `control_bot.py` should use `CONTROL_BOT_TOKEN` when running alongside the collector; otherwise both polling processes will conflict on the same Telegram bot token.
- `/home/fg/ogh` has now been inspected on the VPS. The live website backend is an `admin-api` service listening on `127.0.0.1:3100`.
- The `admin-api` is already connected to PostgreSQL via Prisma on `127.0.0.1:5433` and exposes `POST /api/openclaw/publish`.
- The current runtime blocker is not SSH anymore. It is Telegram polling conflict between the old local collector and the remote collector when both use the same bot token.
