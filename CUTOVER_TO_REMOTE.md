# Cutover To Remote VPS

This guide is for moving the Telegram agent to the remote VPS while keeping the current local agent running until the remote setup is fully ready.

## Goal

- keep the current local agent alive
- prepare the remote server in parallel
- move the old database and old session/state files safely
- connect the remote agent to the website publishing flow later
- do a final cutover only when the remote run is proven healthy

## Phase 1: Keep local as primary

Do not stop the current local agent yet.

While local stays primary:

1. Clone the same repo on the remote server.
2. Create the remote virtualenv.
3. Install Python packages.
4. Prepare `/etc/openclaw/<instance>.env`.
5. Keep remote timers and collector stopped until the data snapshot is copied.

## Phase 2: Create a safe snapshot from local

Create a local snapshot:

```bash
cd /home/dg/openclaw_telegram_agent
python3 create_agent_snapshot.py --output-dir /tmp/openclaw_snapshot_1
```

That snapshot includes:

- `agent.db`
- `control.json` if present
- `bulk_copy_state.json` if present
- `telethon_session*` files if present
- `manifest.json`

## Phase 3: Copy snapshot to remote

When SSH access works:

```bash
cd /home/dg/openclaw_telegram_agent
bash deploy/remote/sync_snapshot_to_remote.sh \
  /tmp/openclaw_snapshot_1 \
  72.60.118.195 \
  4645 \
  fg \
  /home/fg/openclaw_telegram_agent \
  /home/dg/.ssh/openclaw_fg_72_60_118_195
```

## Phase 4: Remote data placement

On the remote VPS, move the snapshot files into the real per-agent paths.

Example for `agent-a`:

```bash
mkdir -p /home/fg/openclaw_telegram_agent/data
cp /home/fg/openclaw_telegram_agent/data/import_snapshot/agent.db /home/fg/openclaw_telegram_agent/data/agent-a.db
cp /home/fg/openclaw_telegram_agent/data/import_snapshot/control.json /home/fg/openclaw_telegram_agent/data/control-agent-a.json
cp /home/fg/openclaw_telegram_agent/data/import_snapshot/bulk_copy_state.json /home/fg/openclaw_telegram_agent/data/bulk_copy_agent_a.json
cp /home/fg/openclaw_telegram_agent/data/import_snapshot/telethon_session.session /home/fg/openclaw_telegram_agent/data/telethon_agent_a.session
```

## Phase 5: Dry run remote without full cutover

Recommended order:

1. Run `post_organized.py --limit 1` manually on remote.
2. Verify website publish or Telegram publish behavior.
3. Start only the control bot if needed.
4. Start timers only after confirming env paths and output targets are correct.

## Phase 6: Final cutover

When remote is healthy:

1. Stop local agent services.
2. Create one final fresh snapshot.
3. Copy the final snapshot to remote.
4. Replace the remote DB/session files.
5. Start remote collector, control bot, RSS timer, and post timer.

That avoids data drift between the old local run and the new remote run.

## OGH note

The current codebase supports generic website publishing via `WEBSITE_PUBLISH_URL`.

Remote inspection on `2026-04-18` confirmed:

- `/home/fg/ogh` exists on the VPS
- the live backend is `apps/admin-api`
- OpenClaw is already configured to call `http://127.0.0.1:3100/api/openclaw/publish`
- the admin API persists posts into PostgreSQL on `127.0.0.1:5433`

So the current safest integration path is:

1. Keep `WEBSITE_PUBLISH_URL` pointed at the local OGH admin API endpoint.
2. Confirm the admin API returns `2xx` only after the PostgreSQL write succeeds.
3. Add content enrichment inside OpenClaw or a new worker before the publish step, rather than bypassing the existing admin API.

## Current runtime blocker

SSH to `72.60.118.195:4645` works.
The current blocker is that the old local collector is still polling Telegram, which causes `Conflict: terminated by other getUpdates request` on the remote collector.
