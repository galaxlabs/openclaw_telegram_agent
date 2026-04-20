#!/usr/bin/env python3
import argparse
import os
import hashlib
import re
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ITEMS_TABLE_SQL = """
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
    processed INTEGER NOT NULL DEFAULT 0,
    processed_at_utc TEXT,
    created_at_utc TEXT NOT NULL
)
"""

REQUIRED_ITEM_COLUMNS = {
    "processed": "INTEGER NOT NULL DEFAULT 0",
    "processed_at_utc": "TEXT",
    "website_published": "INTEGER NOT NULL DEFAULT 0",
    "website_published_at_utc": "TEXT",
    "telegram_published": "INTEGER NOT NULL DEFAULT 0",
    "telegram_published_at_utc": "TEXT",
    "source_deleted": "INTEGER NOT NULL DEFAULT 0",
    "source_deleted_at_utc": "TEXT",
    "publish_error": "TEXT",
    "dedupe_signature": "TEXT",
    "duplicate_of_item_id": "INTEGER",
}

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "si",
}


def _env(env: dict | None = None) -> dict:
    return env if env is not None else os.environ


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def get_db_path(default: str = "agent.db", env: dict | None = None) -> str:
    return _env(env).get("DB_PATH", default)


def get_control_path(default: str = "control.json", env: dict | None = None) -> str:
    return _env(env).get("CONTROL_PATH", default)


def get_bulk_state_file(default: str = "bulk_copy_state.json", env: dict | None = None) -> str:
    return _env(env).get("BULK_STATE_FILE", default)


def get_telethon_session_name(default: str = "telethon_session", env: dict | None = None) -> str:
    return _env(env).get("TELETHON_SESSION_NAME", default)


def parse_post_limit(argv: list[str] | None = None, env: dict | None = None, default: int = 5) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--limit", type=int)
    args, _ = parser.parse_known_args(argv)
    if args.limit is not None:
        return args.limit
    return int(_env(env).get("POST_LIMIT", str(default)))


def normalize_text_for_dedupe(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def normalize_url_for_dedupe(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower().replace("www.", "")
    path = parts.path or ""
    if path != "/":
        path = path.rstrip("/")

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def build_dedupe_signature(title: str | None, url: str | None, note: str | None) -> str:
    normalized_url = normalize_url_for_dedupe(url)
    if normalized_url:
        payload = f"url:{normalized_url}"
    else:
        payload = "text:{title}|{note}".format(
            title=normalize_text_for_dedupe(title),
            note=normalize_text_for_dedupe(note),
        )
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def find_existing_item_by_signature(
    db_path: str,
    signature: str,
    *,
    exclude_item_id: int | None = None,
    require_published: bool = False,
) -> int | None:
    if not signature:
        return None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    conditions = ["dedupe_signature = ?"]
    params: list[object] = [signature]
    if exclude_item_id is not None:
        conditions.append("id != ?")
        params.append(exclude_item_id)

    if require_published:
        conditions.append("(processed = 1 OR website_published = 1 OR telegram_published = 1)")

    query = f"""
        SELECT id
        FROM items
        WHERE {' AND '.join(conditions)}
        ORDER BY id ASC
        LIMIT 1
    """
    row = cur.execute(query, params).fetchone()
    conn.close()
    return int(row[0]) if row else None


def ensure_items_schema(db_path: str) -> set[str]:
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(ITEMS_TABLE_SQL)
    cur.execute("PRAGMA table_info(items)")
    cols = {row[1] for row in cur.fetchall()}

    for col_name, col_sql in REQUIRED_ITEM_COLUMNS.items():
        if col_name not in cols:
            cur.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_sql}")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_url ON items(url_norm)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_title ON items(title_norm)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_dedupe_signature ON items(dedupe_signature)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_source_message ON items(source_chat_id, source_message_id)"
    )
    conn.commit()

    cur.execute("PRAGMA table_info(items)")
    final_cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return final_cols
