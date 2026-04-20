# Remote Cutover Guide

This guide is for moving the Telegram agent to a remote VPS without breaking the current live setup.

## Goal

Keep the current server running while the remote clone is prepared and tested.

## Important rule

Do not let both servers collect from the same live Telegram source chats at the same time.

If both collectors run together, you can get:

- duplicate rows
- duplicate website posts
- duplicate Telegram reposts
- message deletion from the wrong server

## Safe migration order

### Phase 1: Keep the current server live

The current server remains the production collector/publisher.

Do not stop it yet.

### Phase 2: Prepare the remote clone

On the remote VPS:

1. Clone the repo.
2. Create the virtualenv.
3. Install requirements.
4. Restore the migration bundle with the old DB and old runtime files.

Helpful scripts in this repo:

- `scripts/create_migration_bundle.sh`
- `scripts/restore_migration_bundle.sh`

## What to move to the remote server

Move these files if they exist:

- `.env`
- `agent.db`
- `control.json`
- `bulk_copy_state.json`
- `telethon_session.session`
- `config/`
- `data/`

These preserve:

- old database rows
- processed/unprocessed state
- Telethon login session
- control panel state
- bulk copy progress

## Phase 3: Remote safe mode

Before the remote server becomes active, use safe-mode env values:

```env
TELEGRAM_PUBLISH_ENABLED=0
DELETE_SOURCE_AFTER_PUBLISH=0
WEBSITE_PUBLISH_ENABLED=1
WEBSITE_PUBLISH_URL=https://your-site.vercel.app/api/openclaw/publish
WEBSITE_PUBLISH_TOKEN=replace_me
```

In this phase:

- the remote server can test website publishing
- the remote server does not repost to Telegram
- the remote server does not delete source messages
- the current server remains the real production worker

## Phase 4: Connect OGH / Vercel

Current repo support is generic HTTP publishing.

The remote server should call a Vercel API route first.

That route can then:

- write to the real website database
- call `/home/fg/ogh` if needed
- sync into MySQL/MariaDB
- create categories/slugs/pages

See:

- `WEBSITE_PUBLISH_API.md`

## Phase 5: Cutover

Only after remote publishing is verified:

1. Pause or stop the old server.
2. Enable the remote collector.
3. Re-enable Telegram publishing on the remote server if desired.
4. Re-enable source deletion on the remote server if desired.

Suggested final env values:

```env
TELEGRAM_PUBLISH_ENABLED=1
DELETE_SOURCE_AFTER_PUBLISH=1
WEBSITE_PUBLISH_ENABLED=1
```

## Recommended first remote validation commands

```bash
python send_test.py
python post_organized.py --limit 1
systemctl status openclaw-collector@agent-a.service
systemctl status openclaw-post@agent-a.timer
journalctl -u openclaw-post@agent-a.service -n 100 --no-pager
```

## Current blocker

As of 2026-04-18, SSH to `72.60.118.195:4645` is working from this environment.

The current blocker is that the local collector is still live, so the remote collector hits Telegram `getUpdates` conflicts when both use the same bot token.
