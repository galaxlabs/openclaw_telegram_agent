# Remote Runtime Status 2026-04-18

This note captures the live state found during direct inspection of the VPS on `2026-04-18`.

## Confirmed access

- SSH host: `72.60.118.195`
- SSH user: `fg`
- working SSH port: `4645`
- old documented port `4546` times out and should be treated as stale

## Confirmed remote projects

- OpenClaw repo path: `/home/fg/openclaw_telegram_agent`
- website repo path: `/home/fg/ogh`

## Confirmed OGH backend shape

- `ogh` is a monorepo
- `apps/admin-api` is the live backend bridge for OpenClaw
- `apps/admin-api` listens on `127.0.0.1:3100`
- `apps/admin-api` uses Prisma
- Prisma is configured for PostgreSQL
- PostgreSQL is reachable on `127.0.0.1:5433`
- OpenClaw already publishes into `POST /api/openclaw/publish`
- published items are visible from `GET /api/public/posts`

## Confirmed OpenClaw remote shape

- remote OpenClaw currently uses SQLite for collection state
- remote OpenClaw `.env` points `WEBSITE_PUBLISH_URL` to `http://127.0.0.1:3100/api/openclaw/publish`
- `openclaw-collector` is running under PM2
- `openclaw-publisher` exists under PM2 but is currently stopped

## Active blocker

The current blocker is not SSH and not the website backend.

The blocker is Telegram polling conflict:

- local machine still runs `python collector.py`
- remote VPS also runs `openclaw-collector`
- both use the same Telegram bot token
- Telegram returns `Conflict: terminated by other getUpdates request`

## What this means

The website backend is already real and already storing content in PostgreSQL.

So the next build phase should not start by replacing the backend.
It should start by stabilizing cutover and then enriching content before publish.

## Recommended next order

1. Stop the old local collector when ready for real cutover.
2. Keep the website bridge through `apps/admin-api` as the system of record.
3. Keep OpenClaw SQLite only for ingest queue/state unless there is a deliberate migration plan.
4. Add an enrichment pipeline before publish:
   translation
   simplification
   GitHub/repo extraction
   category assignment
   feature extraction
   Urdu output
5. Extend the OGH admin API schema to store enriched fields instead of only flat `title`, `excerpt`, `content`, `category`, and `tags`.
6. Add a review/admin workflow on the website side for approve/edit/publish operations.
7. Only then scale into multiple specialized agents.

## Architecture direction

Recommended responsibility split:

- OpenClaw:
  collect from Telegram, RSS, and supplied URLs
  normalize raw items
  run queued enrichment workers
  send final publish payloads

- OGH admin API:
  authenticate OpenClaw
  validate payloads
  persist canonical content in PostgreSQL
  expose admin and public APIs

- OGH web/admin:
  operator review
  edit before publish
  support multi-language presentation
  support category pages and source-linked posts
