# Website Publish API Contract

This file describes the HTTP payload that `post_organized.py` now sends when website publishing is enabled.

## Goal

Allow the Telegram agent to run on a VPS while publishing cleaned content to a website hosted on Vercel.

The current integration model is:

1. The agent runs on the VPS.
2. The website runs on Vercel.
3. The agent sends a POST request to a Vercel API route.
4. That route stores the content in your real website database or backend flow.

## Required env

```env
WEBSITE_PUBLISH_ENABLED=1
WEBSITE_PUBLISH_URL=https://your-site.vercel.app/api/openclaw/publish
WEBSITE_PUBLISH_TOKEN=replace_me
WEBSITE_PUBLISH_TIMEOUT_SEC=20
```

## HTTP request

Method:

```text
POST
```

Headers:

```text
Content-Type: application/json
Authorization: Bearer <WEBSITE_PUBLISH_TOKEN>
```

## JSON payload

Example payload:

```json
{
  "item_id": 17,
  "title": "Great GitHub repo",
  "url": "https://github.com/openai/openai-python",
  "note": "Useful SDK link with examples",
  "category": "GITHUB",
  "source_domain": "github.com",
  "formatted_text": "Great GitHub repo\nType: GITHUB | Source: github.com\nhttps://github.com/openai/openai-python",
  "source": {
    "chat_id": "-100123",
    "message_id": 88,
    "date_utc": "2026-04-17T20:00:00+00:00"
  }
}
```

## Expected response

Any `2xx` response is treated as success.

Recommended response:

```json
{
  "ok": true,
  "slug": "great-github-repo",
  "id": "post_123"
}
```

## Example curl test

You can test your Vercel route manually from the VPS with:

```bash
curl -X POST "https://your-site.vercel.app/api/openclaw/publish" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "item_id": 17,
    "title": "Great GitHub repo",
    "url": "https://github.com/openai/openai-python",
    "note": "Useful SDK link with examples",
    "category": "GITHUB",
    "source_domain": "github.com",
    "formatted_text": "Great GitHub repo\nType: GITHUB | Source: github.com\nhttps://github.com/openai/openai-python",
    "source": {
      "chat_id": "-100123",
      "message_id": 88,
      "date_utc": "2026-04-17T20:00:00+00:00"
    }
  }'
```

## Recommended Vercel route behavior

Your Vercel API route should:

1. Verify the bearer token.
2. Validate the payload fields.
3. Save the content to your website database.
4. Return a `2xx` response only after the content is safely stored.

That lets the Telegram agent treat the website publish step as complete before moving on to deletion.
