import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse

DB = "agent.db"
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
    # remove any embedded urls
    t = URL_RE.sub("", t).strip()
    # remove repeated domain pieces
    t = re.sub(r"\s+", " ", t).strip()
    # if title becomes empty, fallback to domain
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

def clean_note(note: str | None, title_clean: str, url: str) -> str | None:
    if not note:
        return None
    n = " ".join(note.strip().split())
    # remove urls
    n = URL_RE.sub("", n).strip()
    n = re.sub(r"\s+", " ", n).strip()
    # if note is basically same as title, skip
    if not n:
        return None
    if n.lower() == title_clean.lower():
        return None
    # keep short
    if len(n) > 200:
        n = n[:200] + "…"
    return n

def make_post(title: str, url: str, note: str | None) -> str:
    url = (url or "").strip()
    d = domain_of(url)
    title_clean = clean_title(title, url)
    typ = guess_type(url, title_clean)
    note_clean = clean_note(note, title_clean, url)

    lines = []
    lines.append(f"**{title_clean}**")
    lines.append(f"Type: {typ} | Source: {d if d else 'unknown'}")
    lines.append(url)
    if note_clean:
        lines.append("")
        lines.append(f"Note: {note_clean}")
    return "\n".join(lines)

def main(limit: int = 5):
    con = sqlite3.connect(DB)
    cur = con.cursor()

    rows = cur.execute("""
        SELECT id, title, url, note
        FROM items
        WHERE processed=0
        ORDER BY id ASC
        LIMIT ?
    """, (limit,)).fetchall()

    if not rows:
        print("No unprocessed items left.")
        return

    for (item_id, title, url, note) in rows:
        post = make_post(title, url, note)
        print("=" * 60)
        print(f"ITEM {item_id}")
        print(post)

        cur.execute(
            "UPDATE items SET processed=1, processed_at_utc=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), item_id)
        )

    con.commit()
    con.close()
    print("=" * 60)
    print(f"Marked {len(rows)} items as processed.")

if __name__ == "__main__":
    main()
