#!/usr/bin/env python3
import os
import re
import json
import time
import hashlib
import sqlite3
from datetime import datetime, timezone

import feedparser
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "agent.db")

# Optional: put RSS URLs line-by-line in rss_feeds.txt
FEEDS_FILE = os.getenv("RSS_FEEDS_FILE", "rss_feeds.txt")

# Fallback feeds (used only if rss_feeds.txt not found/empty)
DEFAULT_FEEDS = [
    "https://dev.to/feed/tag/ai",
    "https://dev.to/feed/tag/python",
    "https://towardsdatascience.com/feed",
    "https://www.theverge.com/rss/index.xml",
    "https://arxiv.org/rss/cs.AI",
]

USER_AGENT = os.getenv("RSS_USER_AGENT", "OpenClawRSS/1.0 (+https://example.local)")
SLEEP_BETWEEN_FEEDS_SEC = float(os.getenv("RSS_SLEEP_SEC", "1.0"))

def norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def norm_url(u: str) -> str:
    u = (u or "").strip()
    # remove tracking params crudely
    u = re.sub(r"(\?|&)(utm_[^=]+=[^&]+)", "", u, flags=re.IGNORECASE)
    u = re.sub(r"[?&]+$", "", u)
    return u

def load_feeds() -> list[str]:
    if os.path.exists(FEEDS_FILE):
        urls = []
        with open(FEEDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls.append(line)
        if urls:
            return urls
    return DEFAULT_FEEDS

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def entry_time_iso(entry) -> str:
    # Try published -> updated -> now
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            dt = datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            return dt.isoformat()
    return now_iso()

def pick_title(entry) -> str:
    title = getattr(entry, "title", "") or ""
    title = re.sub(r"\s+", " ", title).strip()
    return title[:300] if title else "(no title)"

def pick_url(entry) -> str:
    # prefer link
    url = getattr(entry, "link", "") or ""
    url = url.strip()
    return url

def ensure_items_table_columns(cur) -> set[str]:
    cur.execute("PRAGMA table_info(items)")
    cols = {row[1] for row in cur.fetchall()}
    return cols

def exists_duplicate(cur, cols: set[str], nurl: str, ntitle: str) -> bool:
    # Support both old/new schemas by checking available columns
    where_parts = []
    params = []

    if "normalized_url" in cols:
        where_parts.append("normalized_url = ?")
        params.append(nurl)
    elif "url" in cols:
        where_parts.append("url = ?")
        params.append(nurl)

    if "normalized_title" in cols:
        where_parts.append("normalized_title = ?")
        params.append(ntitle)
    elif "title" in cols:
        where_parts.append("title = ?")
        params.append(ntitle)

    if not where_parts:
        return False

    sql = "SELECT 1 FROM items WHERE (" + " OR ".join(where_parts) + ") LIMIT 1"
    cur.execute(sql, params)
    return cur.fetchone() is not None

def insert_item(cur, cols: set[str], feed_url: str, title: str, url: str, date_iso: str, raw_json: dict):
    ntitle = norm_text(title)
    nurl = norm_url(url)

    row = {}
    # Try to map to your schema safely
    if "source_chat_id" in cols:
        row["source_chat_id"] = 0  # RSS source (not a telegram chat)
    if "message_id" in cols:
        row["message_id"] = 0
    if "source_message_id" in cols:
        row["source_message_id"] = 0  # RSS source (not from Telegram)
    if "source_date_utc" in cols:
        row["source_date_utc"] = date_iso  # required by your schema
    if "source_platform" in cols:
        row["source_platform"] = "rss"
    if "source_type" in cols:
        row["source_type"] = "rss"
    
    
    if "date" in cols:
        row["date"] = date_iso
        # Some schemas require these timestamps
    if "source_date_utc" in cols:
        row["source_date_utc"] = date_iso
    if "created_at_utc" in cols:
        row["created_at_utc"] = now_iso()
    if "updated_at_utc" in cols:
        row["updated_at_utc"] = now_iso()
    if "source_platform" in cols:
        row["source_platform"] = "rss"
    if "source_type" in cols:
        row["source_type"] = "rss"    
    if "title" in cols:
        row["title"] = title
    if "url" in cols:
        row["url"] = url
    if "note" in cols:
        row["note"] = f"RSS: {feed_url}"
    if "normalized_title" in cols:
        row["normalized_title"] = ntitle
    if "normalized_url" in cols:
        row["normalized_url"] = nurl
    if "processed" in cols:
        row["processed"] = 0
    if "processed_at" in cols:
        row["processed_at"] = None
    if "raw_json" in cols:
        row["raw_json"] = json.dumps(raw_json, ensure_ascii=False)

    # If your table has extra NOT NULL fields, add defaults here:
    if "id" in cols:
        # usually autoincrement, so do not set
        pass

    keys = list(row.keys())
    placeholders = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO items ({','.join(keys)}) VALUES ({placeholders})"
    cur.execute(sql, [row[k] for k in keys])

def fetch_and_save_once():
    feeds = load_feeds()
    if not feeds:
        print("No RSS feeds found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cols = ensure_items_table_columns(cur)

    saved = 0
    dup = 0
    skipped = 0

    for feed_url in feeds:
        print(f"\n[RSS] Fetch: {feed_url}")
        d = feedparser.parse(feed_url, request_headers={"User-Agent": USER_AGENT})

        if getattr(d, "bozo", False):
            # bozo means feed had parsing issues; still may have entries
            err = getattr(d, "bozo_exception", None)
            print(f"  ! parse warning: {err}")

        entries = getattr(d, "entries", []) or []
        print(f"  entries: {len(entries)}")

        for entry in entries:
            title = pick_title(entry)
            url = pick_url(entry)

            if not url:
                skipped += 1
                continue

            url_n = norm_url(url)
            title_n = norm_text(title)

            if exists_duplicate(cur, cols, url_n, title_n):
                dup += 1
                continue

            raw = {
                "feed_url": feed_url,
                "title": title,
                "link": url,
                "published": getattr(entry, "published", None),
                "updated": getattr(entry, "updated", None),
                "summary": getattr(entry, "summary", None),
            }

            insert_item(
                cur=cur,
                cols=cols,
                feed_url=feed_url,
                title=title,
                url=url,
                date_iso=entry_time_iso(entry),
                raw_json=raw,
            )
            saved += 1

        conn.commit()
        time.sleep(SLEEP_BETWEEN_FEEDS_SEC)

    conn.close()
    print(f"\nDONE  saved={saved}  duplicate={dup}  skipped={skipped}")

if __name__ == "__main__":
    fetch_and_save_once()