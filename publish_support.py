#!/usr/bin/env python3
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests


URL_RE = re.compile(r"(https?://[^\s<>\]]+)", re.IGNORECASE)


def _env(env: dict | None = None) -> dict:
    return env if env is not None else os.environ


def env_flag(name: str, default: bool = False, env: dict | None = None) -> bool:
    raw = _env(env).get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def domain_of(url: str) -> str:
    try:
        d = urlparse((url or "").strip()).netloc.lower()
        return d.replace("www.", "")
    except Exception:
        return ""


def clean_title(title: str, url: str) -> str:
    t = (title or "").strip()
    u = (url or "").strip()
    t = URL_RE.sub("", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        d = domain_of(u)
        return d if d else "(No title)"
    return t[:160]


def guess_type(url: str, title: str) -> str:
    u = (url or "").lower()
    t = (title or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "VIDEO"
    if "github.com" in u:
        return "GITHUB"
    if any(x in u for x in ["medium.com", "dev.to", "towardsdatascience.com", "substack.com"]):
        return "ARTICLE"
    if any(x in u for x in ["twitter.com", "x.com", "threads.net", "instagram.com", "facebook.com"]):
        return "SOCIAL"
    if any(x in t for x in ["tutorial", "course", "guide", "how to"]):
        return "TUTORIAL"
    return "LINK"


def clean_note(note: str | None, title_clean: str) -> str | None:
    if not note:
        return None
    n = " ".join(note.strip().split())
    n = URL_RE.sub("", n).strip()
    n = re.sub(r"\s+", " ", n).strip()
    if not n:
        return None
    if n.lower() == title_clean.lower():
        return None
    if len(n) > 400:
        n = n[:400] + "…"
    return n


def make_post(title: str, url: str, note: str | None) -> str:
    url = (url or "").strip()
    title_clean = clean_title(title, url)
    typ = guess_type(url, title_clean)
    note_clean = clean_note(note, title_clean)
    source_domain = domain_of(url)

    lines = [
        title_clean,
        f"Type: {typ} | Source: {source_domain if source_domain else 'unknown'}",
        url,
    ]
    if note_clean:
        lines.extend(["", f"Note: {note_clean}"])
    return "\n".join(lines)


def get_publish_config(env: dict | None = None) -> dict[str, Any]:
    source_env = _env(env)
    bot_token = source_env.get("TELEGRAM_BOT_TOKEN", "").strip()
    target_chat_id = source_env.get("TELEGRAM_TARGET_CHAT_ID", "").strip()
    website_url = source_env.get("WEBSITE_PUBLISH_URL", "").strip()

    website_enabled = env_flag(
        "WEBSITE_PUBLISH_ENABLED",
        default=bool(website_url),
        env=source_env,
    )
    if website_enabled and not website_url:
        raise ValueError("WEBSITE_PUBLISH_ENABLED is set but WEBSITE_PUBLISH_URL is missing.")

    telegram_enabled = env_flag(
        "TELEGRAM_PUBLISH_ENABLED",
        default=bool(bot_token and target_chat_id),
        env=source_env,
    )
    telegram_enabled = telegram_enabled and bool(bot_token and target_chat_id)

    delete_enabled = env_flag("DELETE_SOURCE_AFTER_PUBLISH", default=True, env=source_env)
    delete_enabled = delete_enabled and bool(bot_token)

    return {
        "bot_token": bot_token,
        "target_chat_id": target_chat_id,
        "website_enabled": website_enabled,
        "website_url": website_url,
        "website_token": source_env.get("WEBSITE_PUBLISH_TOKEN", "").strip(),
        "website_timeout_sec": float(source_env.get("WEBSITE_PUBLISH_TIMEOUT_SEC", "20")),
        "telegram_enabled": telegram_enabled,
        "delete_enabled": delete_enabled,
    }


def build_website_payload(item: dict[str, Any], formatted_text: str) -> dict[str, Any]:
    url = (item.get("url") or "").strip()
    title_clean = clean_title(item.get("title") or "", url)
    note_clean = clean_note(item.get("note"), title_clean)
    category = guess_type(url, title_clean)

    return {
        "item_id": item.get("id"),
        "title": title_clean,
        "url": url,
        "note": note_clean,
        "category": category,
        "source_domain": domain_of(url),
        "formatted_text": formatted_text,
        "source": {
            "chat_id": str(item.get("source_chat_id") or ""),
            "message_id": item.get("source_message_id"),
            "date_utc": item.get("source_date_utc"),
        },
    }


def publish_to_website(
    item: dict[str, Any],
    formatted_text: str,
    env: dict | None = None,
) -> dict[str, Any]:
    cfg = get_publish_config(env)
    if not cfg["website_enabled"]:
        return {"skipped": True}

    payload = build_website_payload(item, formatted_text)
    headers = {"Content-Type": "application/json"}
    if cfg["website_token"]:
        headers["Authorization"] = f"Bearer {cfg['website_token']}"

    response = requests.post(
        cfg["website_url"],
        json=payload,
        headers=headers,
        timeout=cfg["website_timeout_sec"],
    )
    response.raise_for_status()

    body = response.text.strip()
    if len(body) > 2000:
        body = body[:2000] + "...(trimmed)"

    return {
        "status_code": response.status_code,
        "body": body,
        "payload": payload,
    }


def is_item_fully_processed(
    *,
    item: dict[str, Any],
    website_enabled: bool,
    telegram_enabled: bool,
    delete_enabled: bool,
) -> bool:
    website_done = (not website_enabled) or bool(item.get("website_published"))
    telegram_done = (not telegram_enabled) or bool(item.get("telegram_published"))
    delete_done = (not delete_enabled) or bool(item.get("source_deleted"))
    return website_done and telegram_done and delete_done
