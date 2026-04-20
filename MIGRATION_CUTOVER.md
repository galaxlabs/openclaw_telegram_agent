# OpenClaw No-Break Migration Guide

This guide is for moving the Telegram agent to the VPS while keeping the current local server running until the remote side is fully ready.

## Current local runtime found on 2026-04-17

Local processes already active:

- `python collector.py`
- a shell loop running `python rss_collector.py` and `python post_organized.py --limit 5` every 10 minutes

This means the local system is currently the live system and should remain the source of truth until the VPS passes checks.

## Important rule

Do not run the remote collector and remote posting timers against the same production Telegram chats until the VPS is verified.

Otherwise you risk:

- duplicate collection
- duplicate publishing
- premature source-message deletion

## Safe migration phases

### Phase 1: Prepare the VPS only

SSH access is now confirmed on port `4645`:

```bash
ssh -i ~/.ssh/openclaw_fg_72_60_118_195 -p 4645 fg@72.60.118.195
cd /home/fg
git clone https://github.com/galaxlabs/openclaw_telegram_agent.git
cd openclaw_telegram_agent
bash scripts/bootstrap_remote.sh
```

Or install from a specific branch / ref:

```bash
REPO_REF=main bash scripts/bootstrap_remote.sh
```

At this phase:

- clone repo
- create virtualenv
- install Python packages
- create `data`, `config`, and `logs`
- do not start production services yet

### Phase 2: Configure a staging agent on the VPS

Create:

```bash
sudo mkdir -p /etc/openclaw
sudo cp deploy/examples/agent-stage.env.example /etc/openclaw/agent-stage.env
sudo nano /etc/openclaw/agent-stage.env
```

Recommended staging behavior:

- `TELEGRAM_PUBLISH_ENABLED=0`
- `DELETE_SOURCE_AFTER_PUBLISH=0`
- `WEBSITE_PUBLISH_ENABLED=1`
- use a separate staging DB path

That lets the VPS publish to the website endpoint without affecting the production Telegram flow.

### Phase 3: Verify the website endpoint first

From the VPS:

```bash
curl -X POST "https://your-site.vercel.app/api/openclaw/publish" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "item_id": 1,
    "title": "Connectivity test",
    "url": "https://example.com/test",
    "note": "sent from VPS staging",
    "category": "LINK",
    "source_domain": "example.com",
    "formatted_text": "Connectivity test\nType: LINK | Source: example.com\nhttps://example.com/test",
    "source": {
      "chat_id": "0",
      "message_id": 0,
      "date_utc": "2026-04-17T00:00:00+00:00"
    }
  }'
```

Only continue after the website returns a clean `2xx` response and stores the data correctly.

### Phase 4: Inspect `/home/fg/ogh`

Remote inspection on `2026-04-18` found:

- `ogh` is a monorepo with `apps/web`, `apps/pocketbase`, and `apps/admin-api`
- the live OpenClaw bridge is `apps/admin-api`
- `apps/admin-api` uses Prisma with PostgreSQL
- the live publish endpoint is `POST http://127.0.0.1:3100/api/openclaw/publish`

If `ogh` already owns the content model, the OpenClaw agent should publish into that contract rather than inventing a second backend.

### Phase 5: Remote staging start

After env is ready:

```bash
sudo cp deploy/systemd/openclaw-*.service /etc/systemd/system/
sudo cp deploy/systemd/openclaw-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-control-bot@agent-stage.service
```

For staging, start only what you need for testing.

Avoid starting:

- `openclaw-collector@agent-stage.service`
- `openclaw-rss@agent-stage.timer`
- `openclaw-post@agent-stage.timer`

unless the staging env points to isolated chats and isolated data.

### Phase 6: Production cutover

When the VPS is confirmed good:

1. Stop local live jobs.
2. Start remote production jobs.
3. Watch logs closely for duplicate or failed posts.

Local stop examples:

```bash
pkill -f "python collector.py"
pkill -f "python rss_collector.py"
pkill -f "python post_organized.py --limit 5"
```

Remote production start examples:

```bash
sudo cp deploy/examples/agent-prod.env.example /etc/openclaw/agent-prod.env
sudo nano /etc/openclaw/agent-prod.env
sudo systemctl enable --now openclaw-collector@agent-prod.service
sudo systemctl enable --now openclaw-control-bot@agent-prod.service
sudo systemctl enable --now openclaw-rss@agent-prod.timer
sudo systemctl enable --now openclaw-post@agent-prod.timer
```

### Phase 7: Rollback

If remote production misbehaves:

1. Stop the remote production services immediately.
2. Restart the known-good local collector and local cron loop.
3. Review `publish_error` values in the remote DB.

## Current blocker

As of 2026-04-18, SSH to `72.60.118.195:4645` is working from this environment.

The current blocker is runtime overlap: the old local collector is still running and conflicts with the remote collector over Telegram long polling.
