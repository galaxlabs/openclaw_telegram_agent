#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import timezone
from dotenv import load_dotenv

from telethon import TelegramClient
import re
from runtime_support import ensure_parent_dir, get_bulk_state_file, get_telethon_session_name

URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

# Loads .env if present (optional)
load_dotenv(dotenv_path=".env")

API_ID = int(os.getenv("TELEGRAM_API_ID", "312225"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "dbffd181aa0a5bd040a806c410ee81a9")

# Defaults (you can change later)
DEFAULT_SOURCE_CHAT_ID = int(os.getenv("BULK_SOURCE_CHAT_ID", "-1001220278770"))  # Technical
DEFAULT_TARGET_CHAT_ID = int(os.getenv("BULK_TARGET_CHAT_ID", "-1003734446596"))  # IT Space

STATE_FILE = get_bulk_state_file("bulk_copy_state.json")
SESSION_NAME = get_telethon_session_name("telethon_session")

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state: dict):
    ensure_parent_dir(STATE_FILE)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def msg_text(m) -> str:
    # Text or caption
    t = (m.message or "").strip()
    return t

async def main():
    if not API_ID or not API_HASH:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH")

    ensure_parent_dir(SESSION_NAME)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    state = load_state()
    source_id = DEFAULT_SOURCE_CHAT_ID
    target_id = DEFAULT_TARGET_CHAT_ID

    # Resume: copy only messages with id > last_id
    last_id = int(state.get(str(source_id), 0))

    # How many to scan per run (you can increase)
    LIMIT = int(os.getenv("BULK_LIMIT", "500"))
    SLEEP_SEC = float(os.getenv("BULK_SLEEP_SEC", "0.7"))

    await client.start()  # first time: asks phone + code in terminal

    source = await client.get_entity(source_id)
    target = await client.get_entity(target_id)

    # Fetch newest first, then reverse to send oldest->newest
    msgs = []
    async for m in client.iter_messages(source, limit=LIMIT):
        if m.id <= last_id:
            continue
        t = msg_text(m)
        if not t:
            continue  # skip empty / media-only
        if not URL_RE.search(t):
            continue  # links only
        msgs.append(m)

    msgs.reverse()

    if not msgs:
        print(f"No new text messages to copy. (last_id={last_id})")
        return

    print(f"Copying {len(msgs)} messages from {source_id} -> {target_id} (text-only)")
    copied = 0

    for m in msgs:
        text = msg_text(m)
        # Add original date (optional but helpful)
        dt = m.date.replace(tzinfo=timezone.utc).isoformat() if m.date else ""
        out = text
        if dt:
            out = f"{text}\n\n[Copied from source | {dt}]"

        await client.send_message(target, out, link_preview=True)

        try:
            await client.delete_messages(source, [m.id])
            print(f"DELETED source msg {m.id}")
        except Exception as e:
            print(f"WARN: delete failed for msg {m.id}: {e}")


        copied += 1
        last_id = max(last_id, m.id)

        # Save progress every 20 messages
        if copied % 20 == 0:
            state[str(source_id)] = last_id
            save_state(state)
            print(f"Progress: copied={copied}, last_id={last_id}")

        await asyncio.sleep(SLEEP_SEC)

    state[str(source_id)] = last_id
    save_state(state)
    print(f"DONE copied={copied}, new last_id={last_id}")

if __name__ == "__main__":
    asyncio.run(main())
