import os
import re
import sqlite3
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

DB = "agent.db"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SOURCE_CHAT_ID = os.getenv("TELEGRAM_SOURCE_CHAT_ID")  # kept for reference
TARGET_CHAT_ID = os.getenv("TELEGRAM_TARGET_CHAT_ID")

if not TOKEN or not TARGET_CHAT_ID:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_TARGET_CHAT_ID in .env")

URL_RE = re.compile(r"(https?://[^\s<>\]]+)", re.IGNORECASE)

def domain_of(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
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
    if len(n) > 200:
        n = n[:200] + "…"
    return n

def make_post(title: str, url: str, note: str | None) -> str:
    url = (url or "").strip()
    d = domain_of(url)
    title_clean = clean_title(title, url)
    typ = guess_type(url, title_clean)
    note_clean = clean_note(note, title_clean)

    lines = []
    # Telegram supports MarkdownV2; but to keep it simple, we use plain text.
    lines.append(f"{title_clean}")
    lines.append(f"Type: {typ} | Source: {d if d else 'unknown'}")
    lines.append(url)
    if note_clean:
        lines.append("")
        lines.append(f"Note: {note_clean}")
    return "\n".join(lines)

def fetch_unprocessed(limit: int):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rows = cur.execute("""
        SELECT id, title, url, note, source_chat_id, source_message_id
        FROM items
        WHERE processed=0 AND url IS NOT NULL
        ORDER BY (source_chat_id=0) ASC, id ASC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return rows

def mark_processed(ids):
    if not ids:
        return
    con = sqlite3.connect(DB)
    cur = con.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.executemany("UPDATE items SET processed=1, processed_at_utc=? WHERE id=?", [(now, i) for i in ids])
    con.commit()
    con.close()

async def main(limit: int = 5):
    rows = fetch_unprocessed(limit)
    if not rows:
        print("No unprocessed items to post.")
        return

    bot = Bot(TOKEN)
    done_ids = []

    for item_id, title, url, note, src_chat_id, src_msg_id in rows:
        text = make_post(title, url, note)
        await bot.send_message(chat_id=TARGET_CHAT_ID, text=text, disable_web_page_preview=False)
        print("POSTED item", item_id)
        done_ids.append(item_id)

        try:
            if str(src_chat_id) != 0 and int(src_msg_id) > 0:
                await bot.delete_message(
                    chat_id=int(src_chat_id),
                    message_id=int(src_msg_id)
                )
                print("DELETED source message", src_msg_id, "from", src_chat_id)
        except Exception as e:
            print("WARN: could not delete source message:", e)


    mark_processed(done_ids)
    print("Marked processed:", len(done_ids))

if __name__ == "__main__":
    asyncio.run(main())
