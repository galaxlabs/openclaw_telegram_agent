# OpenClaw Telegram Agent Project Memory

## 1. Project purpose in simple words

This project is a Telegram content pipeline with an optional external website publishing step.

Today it does these jobs:

1. Watch one or more Telegram source groups/channels.
2. Collect links and notes from those messages.
3. Save them into a local database.
4. Optionally collect RSS feed items into the same database.
5. Reformat saved items into a cleaner post.
6. Optionally publish them to an external website endpoint such as a Vercel API route.
7. Optionally publish them to a target Telegram chat.
8. Delete the original Telegram source message after the enabled publish steps succeed.

The codebase is already moving toward a multi-agent setup, but right now it is still a Telegram-to-database-to-Telegram pipeline, not yet a Telegram-to-website/MySQL publishing system.

## 2. Current runtime architecture

### Active runtime roles

- `collector.py`
  Main Telegram bot listener.
  Watches `TELEGRAM_SOURCE_CHAT_IDS` and stores links or notes in the database.

- `rss_collector.py`
  Pulls RSS feed entries and stores them in the same database.
  RSS items are marked with `source_chat_id = 0` and `source_message_id = 0`.

- `post_organized.py`
  Reads unprocessed database items, formats them into cleaner posts, can publish them to a website endpoint, can send them to `TELEGRAM_TARGET_CHAT_ID`, and only marks them processed after the enabled steps finish.

- `publish_support.py`
  Shared publishing logic.
  Builds the website payload, resolves publish mode from env, posts to the website endpoint, and decides when an item is fully processed.

- `control_bot.py`
  A small control panel bot.
  Supports pause/resume, stats, and manual `postnow`.
  It should use a separate bot token if it runs in parallel with the collector.

### Support / utility roles

- `runtime_support.py`
  Shared runtime helpers.
  Handles database path, control file path, Telethon session path, bulk state path, post limit, and auto-creation / migration of the SQLite schema.

- `bulk_copy.py`
  Telethon-based bulk mover for text messages with links.
  Intended for backlog copy/migration from one Telegram chat to another.
  Deletes source messages after copying.

- `organize_preview.py`
  Dry-run style preview tool.
  Prints how posts would look and marks them processed.

- `send_test.py`
  Sends a test message to the target Telegram chat.

- `get_chat_id.py`
  Prints Telegram chat IDs when messages arrive.

## 3. Database reality

Current live storage is SQLite, not MySQL.

The main table is `items` inside the file defined by `DB_PATH`.

Important columns:

- `source_chat_id`
- `source_message_id`
- `source_date_utc`
- `title`
- `title_norm`
- `url`
- `url_norm`
- `note`
- `raw_json`
- `processed`
- `processed_at_utc`
- `website_published`
- `website_published_at_utc`
- `telegram_published`
- `telegram_published_at_utc`
- `source_deleted`
- `source_deleted_at_utc`
- `publish_error`
- `created_at_utc`

What this means:

- The app is already safe for multiple named agents if each agent gets its own separate file paths.
- The code does not currently talk to MySQL or MariaDB.
- The code does not currently write into `/home/fg/ogh`.

## 4. Multi-agent support status

### What already exists

The repo already supports multiple named instances through per-agent env files and templated systemd units:

- `deploy/systemd/openclaw-collector@.service`
- `deploy/systemd/openclaw-control-bot@.service`
- `deploy/systemd/openclaw-post@.service`
- `deploy/systemd/openclaw-post@.timer`
- `deploy/systemd/openclaw-rss@.service`
- `deploy/systemd/openclaw-rss@.timer`

Each agent instance can have its own:

- `DB_PATH`
- `CONTROL_PATH`
- `RSS_FEEDS_FILE`
- `TELETHON_SESSION_NAME`
- `BULK_STATE_FILE`
- source chat IDs
- target chat ID

### What does not exist yet

These future roles are not implemented yet:

- translator agent
- simplifier / explained-words agent
- example generator agent
- tech/category extractor agent
- GitHub link extractor
- website publisher into `/home/fg/ogh`
- MySQL-backed storage
- workflow for deleting Telegram content only after confirmed website publish

## 5. Current data flow

### Telegram collection flow

1. A message arrives in one of the allowed source chats.
2. `collector.py` extracts URLs and basic title/note text.
3. Each URL becomes one row in SQLite.
4. `post_organized.py` reads unprocessed rows.
5. It builds a cleaner formatted post:
   title
   type guess like `GITHUB`, `VIDEO`, `ARTICLE`, `SOCIAL`, `TUTORIAL`, `LINK`
   source domain
   URL
   shortened note
6. If website publishing is enabled, the item is POSTed to the website endpoint first.
7. If Telegram publishing is enabled, the cleaned post is sent to the target Telegram chat.
8. If source deletion is enabled, the source Telegram message is deleted after the publish steps succeed.
9. The row is marked `processed=1` only after all enabled steps finish.

### RSS flow

1. `rss_collector.py` loads feeds from `RSS_FEEDS_FILE` or fallback defaults.
2. New RSS entries are normalized and deduplicated.
3. Entries are saved into the same `items` table.
4. `post_organized.py` later publishes them to the target Telegram chat.
5. RSS source deletion is skipped because RSS rows have source IDs set to zero.

## 6. What is active vs planned

### Active now

- Telegram source monitoring
- multi-source chat support
- SQLite storage
- RSS ingest
- optional website publish via HTTP endpoint
- Telegram publish to target chat
- control panel commands
- multi-instance deployment pattern
- local schema auto-migration

### Planned / requested but not built yet

- publish categorized content on websites
- save into MySQL / MariaDB
- integrate with backend project at `/home/fg/ogh`
- AI rewrite into simpler explained words
- add examples and technical explanation
- collect GitHub links separately
- keep multiple specialized agents in one broader pipeline

## 7. Important operational behavior

### Deletion behavior

Deletion is already active in two places:

- `post_organized.py` tries to delete the original source Telegram message after successful publish.
- `bulk_copy.py` tries to delete the source message after copying.

If the long-term plan is "publish to website first, then delete from Telegram", this logic must be changed before website publishing goes live.

### Coexistence with Frappe / ERPNext

This project is friendly to a shared VPS if we keep it isolated:

- run it under its own directory: `/home/fg/openclaw_telegram_agent`
- use its own virtualenv
- use systemd units with unique names
- do not bind any web port for this repo unless website integration is added later
- do not touch existing Frappe services, benches, nginx config, or Redis workers

In the current codebase, this project is mostly background jobs and Telegram bots, so it should not directly conflict with ERPNext unless we later add a web API or website worker.

## 8. Environment and config memory

Main env variables from `.env.example`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_TARGET_CHAT_ID`
- `TELEGRAM_SOURCE_CHAT_IDS`
- `TELEGRAM_SOURCE_CHAT_ID` (legacy single-source fallback)
- `DB_PATH`
- `CONTROL_PATH`
- `POST_LIMIT`
- `RSS_FEEDS_FILE`
- `RSS_SLEEP_SEC`
- `RSS_USER_AGENT`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELETHON_SESSION_NAME`
- `BULK_STATE_FILE`
- `BULK_SOURCE_CHAT_ID`
- `BULK_TARGET_CHAT_ID`
- `BULK_LIMIT`
- `BULK_SLEEP_SEC`

For multi-agent deployment, every agent must use different storage file paths.

## 9. Known code / design gaps

- No MySQL or MariaDB adapter exists yet.
- No ORM exists yet.
- No pull API exists yet for a website backend to read from SQLite directly.
- No direct integration with `/home/fg/ogh` exists yet.
- No category table or content model exists yet beyond the flat `items` table.
- No `/home/fg/ogh`-specific adapter exists yet; current support is generic HTTP publishing.
- No queue/job orchestration exists for future specialized agents.
- `bulk_copy.py` currently contains default Telethon API values and should rely on env-only secrets before production rollout.

## 10. Local repository status at inspection time

Observed locally on `2026-04-17`:

- Git remote: `https://github.com/galaxlabs/openclaw_telegram_agent.git`
- Local tests passed: `python3 -m unittest discover -s tests`
- The working tree is dirty with ongoing local edits and new deployment files.
- There is a large local SQLite file: `agent.db`

That large local DB should not be copied blindly to a new VPS if the plan is to start fresh per-agent databases.

## 11. Remote VPS status at inspection time

Target VPS details:

- host: `72.60.118.195`
- user: `fg`
- ssh port: `4645`

SSH was verified from this environment on `2026-04-18`.

Remote inspection confirmed:

- `/home/fg/openclaw_telegram_agent` exists on the VPS
- `/home/fg/ogh` exists on the VPS
- `ogh` contains `apps/admin-api`, `apps/web`, and `apps/pocketbase`
- `apps/admin-api` is running on port `3100`
- `apps/admin-api` uses Prisma with PostgreSQL via `127.0.0.1:5433`
- OpenClaw on the VPS is configured to publish to `http://127.0.0.1:3100/api/openclaw/publish`
- published content is already visible through `GET /api/public/posts`
- PM2 is being used on the VPS for `openclaw-collector` and `openclaw-publisher`
- the remote collector is currently conflicting with another bot instance because both are polling the same Telegram token

## 12. Recommended next build order

To grow this into the requested multi-agent website publisher safely, the best order is:

1. Reach the VPS over SSH and inspect existing services.
2. Stop the old local collector before enabling the remote collector against the same Telegram bot token.
3. Keep OpenClaw publishing through the existing internal OGH API instead of writing directly to the website database from Python.
4. Add a normalized content model for categories, links, source metadata, publish status, and delete status.
5. Add content-enrichment stages before website publish:
   translate
   simplify
   add examples
   extract tech topics
   detect GitHub links
   assign categories
6. Expand the admin API schema so enriched fields and editorial status are stored explicitly.
7. Add a website publishing worker.
8. Then enable multi-agent production rollout on the VPS.

## 13. Short summary

This repo is already a good base for multi-source Telegram and RSS collection, multi-instance deployment, and Telegram reposting.

It is not yet a MySQL-backed, website-publishing, multi-agent content system.

That next phase depends on stopping the old local collector cleanly and then adding the enrichment workflow on top of the already-working OGH admin API bridge.
