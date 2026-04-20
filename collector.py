import os
import re
import json
import time
import sqlite3
import hashlib
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from runtime_support import (
    build_dedupe_signature,
    ensure_items_schema,
    ensure_parent_dir,
    get_db_path,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TELEGRAM_TARGET_CHAT_ID")  # not used yet, later
SOURCE_CHAT_ID = os.getenv("TELEGRAM_SOURCE_CHAT_ID")  # legacy single source
SOURCE_CHAT_IDS_RAW = os.getenv("TELEGRAM_SOURCE_CHAT_IDS", "").strip()
AUTO_REGISTER_SOURCE_CHATS = os.getenv("AUTO_REGISTER_SOURCE_CHATS", "1").strip().lower() in {"1", "true", "yes", "on"}
SOURCE_CHAT_REGISTRY = os.getenv("SOURCE_CHAT_REGISTRY", os.path.join(os.path.dirname(__file__), "data", "source_chats.json"))

def parse_source_ids(raw: str, single: str | None) -> set[str]:
    ids = set()
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part:
                ids.add(part)
    if single:
        ids.add(str(single).strip())
    return ids


def load_registered_source_ids() -> set[str]:
    if not os.path.exists(SOURCE_CHAT_REGISTRY):
        return set()
    try:
        with open(SOURCE_CHAT_REGISTRY, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return {str(item.get("id")) for item in payload if isinstance(item, dict) and item.get("id")}
    except Exception:
        return set()
    return set()


def persist_source_chat(chat) -> None:
    ensure_parent_dir(SOURCE_CHAT_REGISTRY)
    existing = []
    if os.path.exists(SOURCE_CHAT_REGISTRY):
        try:
            with open(SOURCE_CHAT_REGISTRY, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except Exception:
            existing = []

    chat_id = str(chat.id)
    if any(str(item.get("id")) == chat_id for item in existing if isinstance(item, dict)):
        return

    existing.append({
        "id": chat_id,
        "title": getattr(chat, "title", None) or getattr(chat, "full_name", None) or "Unknown chat",
        "type": getattr(chat, "type", None),
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
    })

    with open(SOURCE_CHAT_REGISTRY, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, ensure_ascii=False, indent=2)

SOURCE_CHAT_IDS = parse_source_ids(SOURCE_CHAT_IDS_RAW, SOURCE_CHAT_ID)
SOURCE_CHAT_IDS.update(load_registered_source_ids())

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN. Check .env")


DB_PATH = get_db_path(os.path.join(os.path.dirname(__file__), "agent.db"))

URL_RE = re.compile(r"(https?://[^\s<>\]]+)", re.IGNORECASE)

def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip()).lower()

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def init_db():
    ensure_items_schema(DB_PATH)

def source_message_seen(source_chat_id: str, source_message_id: int) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT 1 FROM items WHERE source_chat_id=? AND source_message_id=? LIMIT 1",
        (source_chat_id, source_message_id),
    )
    seen = cur.fetchone() is not None
    con.close()
    return seen


def already_seen(url_norm: str | None, title_norm: str | None, signature: str | None = None) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if url_norm:
        cur.execute("SELECT 1 FROM items WHERE url_norm=? LIMIT 1", (url_norm,))
        if cur.fetchone():
            con.close()
            return True
    if title_norm:
        cur.execute("SELECT 1 FROM items WHERE title_norm=? LIMIT 1", (title_norm,))
        if cur.fetchone():
            con.close()
            return True
    if signature:
        cur.execute("SELECT 1 FROM items WHERE dedupe_signature=? LIMIT 1", (signature,))
        if cur.fetchone():
            con.close()
            return True
    con.close()
    return False

def save_item(*, source_chat_id: str, source_message_id: int, source_date_utc: str,
              title: str | None, url: str | None, note: str | None, raw: dict):
    title_norm = norm_title(title) if title else None
    url_norm = (url or "").strip().lower() if url else None
    dedupe_signature = build_dedupe_signature(title, url, note)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO items (
            source_chat_id, source_message_id, source_date_utc,
            title, title_norm, url, url_norm, note,
            fp_title, fp_url, raw_json, created_at_utc, dedupe_signature
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        source_chat_id,
        source_message_id,
        source_date_utc,
        title,
        title_norm,
        url,
        url_norm,
        note,
        fingerprint(title_norm) if title_norm else None,
        fingerprint(url_norm) if url_norm else None,
        json.dumps(raw, ensure_ascii=False),
        datetime.now(timezone.utc).isoformat(),
        dedupe_signature,
    ))
    con.commit()
    con.close()

def extract_title_and_urls(text: str):
    text = text or ""
    urls = URL_RE.findall(text)
    # title heuristic: first non-empty line, trimmed
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0][:180] if lines else None
    return title, urls

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    if not chat or not msg:
        return

    chat_id = str(chat.id)
    if TARGET_CHAT_ID and chat_id == str(TARGET_CHAT_ID).strip():
        return

    sender = getattr(msg, "from_user", None)
    if sender and getattr(sender, "is_bot", False):
        return

    if chat_id not in SOURCE_CHAT_IDS:
        if not AUTO_REGISTER_SOURCE_CHATS:
            return
        SOURCE_CHAT_IDS.add(chat_id)
        persist_source_chat(chat)
        print(f"REGISTERED SOURCE CHAT: {chat_id} | {getattr(chat, 'title', 'Unknown chat')}")

    if source_message_seen(chat_id, msg.message_id):
        print("DUPLICATE SOURCE MESSAGE:", msg.message_id, "from", chat.id)
        return

    text = (msg.text or msg.caption or "").strip()
    if not text and not msg.forward_origin:
        return

    title, urls = extract_title_and_urls(text)

    # If no URL, still store as "note"
    if not urls:
        title_norm = norm_title(title) if title else None
        signature = build_dedupe_signature(title, None, text[:2000] if text else None)
        if already_seen(None, title_norm, signature):
            print("DUPLICATE (title):", title)
            return
        save_item(
            source_chat_id=str(chat.id),
            source_message_id=msg.message_id,
            source_date_utc=(msg.date.replace(tzinfo=timezone.utc).isoformat() if msg.date else datetime.now(timezone.utc).isoformat()),
            title=title,
            url=None,
            note=text[:2000] if text else None,
            raw=update.to_dict()
        )
        print("SAVED NOTE:", title)
        return

    # Store each URL as separate item
    seen_urls_in_message = set()
    for url in urls[:10]:
        url_norm = url.strip().lower()
        if url_norm in seen_urls_in_message:
            print("DUPLICATE IN SAME MESSAGE:", url)
            continue
        seen_urls_in_message.add(url_norm)

        title_norm = norm_title(title) if title else None
        signature = build_dedupe_signature(title, url, text[:2000] if text else None)
        if already_seen(url_norm, title_norm, signature):
            print("DUPLICATE:", url)
            continue

        save_item(
            source_chat_id=str(chat.id),
            source_message_id=msg.message_id,
            source_date_utc=(msg.date.replace(tzinfo=timezone.utc).isoformat() if msg.date else datetime.now(timezone.utc).isoformat()),
            title=title,
            url=url,
            note=text[:2000] if text else None,
            raw=update.to_dict()
        )
        print("SAVED:", url)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handler))
    print("Collector running.")
    print("Auto-register source chats:", "enabled" if AUTO_REGISTER_SOURCE_CHATS else "disabled")
    print("Known source chats:", ", ".join(sorted(SOURCE_CHAT_IDS)) if SOURCE_CHAT_IDS else "No chats registered yet")
    print("Add the bot to the relevant groups/channels and send or post content there.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
