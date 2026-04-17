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

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TELEGRAM_TARGET_CHAT_ID")  # not used yet, later
SOURCE_CHAT_ID = os.getenv("TELEGRAM_SOURCE_CHAT_ID")  # legacy single source
SOURCE_CHAT_IDS_RAW = os.getenv("TELEGRAM_SOURCE_CHAT_IDS", "").strip()

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

SOURCE_CHAT_IDS = parse_source_ids(SOURCE_CHAT_IDS_RAW, SOURCE_CHAT_ID)

if not TOKEN or not SOURCE_CHAT_IDS:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_SOURCE_CHAT_ID(S). Check .env")


DB_PATH = os.path.join(os.path.dirname(__file__), "agent.db")

URL_RE = re.compile(r"(https?://[^\s<>\]]+)", re.IGNORECASE)

def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip()).lower()

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat_id TEXT NOT NULL,
            source_message_id INTEGER NOT NULL,
            source_date_utc TEXT NOT NULL,
            title TEXT,
            title_norm TEXT,
            url TEXT,
            url_norm TEXT,
            note TEXT,
            fp_title TEXT,
            fp_url TEXT,
            raw_json TEXT,
            created_at_utc TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_url ON items(url_norm)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_title ON items(title_norm)")
    con.commit()
    con.close()

def already_seen(url_norm: str | None, title_norm: str | None) -> bool:
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
    con.close()
    return False

def save_item(*, source_chat_id: str, source_message_id: int, source_date_utc: str,
              title: str | None, url: str | None, note: str | None, raw: dict):
    title_norm = norm_title(title) if title else None
    url_norm = (url or "").strip().lower() if url else None

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO items (
            source_chat_id, source_message_id, source_date_utc,
            title, title_norm, url, url_norm, note,
            fp_title, fp_url, raw_json, created_at_utc
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
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
        datetime.now(timezone.utc).isoformat()
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

    # Only process the Source channel/group
    if not chat or str(chat.id) not in SOURCE_CHAT_IDS:
        return

    text = (msg.text or msg.caption or "").strip()
    if not text and not msg.forward_origin:
        return

    title, urls = extract_title_and_urls(text)

    # If no URL, still store as "note"
    if not urls:
        title_norm = norm_title(title) if title else None
        if already_seen(None, title_norm):
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
    for url in urls[:10]:
        url_norm = url.strip().lower()
        title_norm = norm_title(title) if title else None
        if already_seen(url_norm, title_norm):
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
    print("Source chats:", ", ".join(sorted(SOURCE_CHAT_IDS)))
    print("Forward links/notes into your AI channel now...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
