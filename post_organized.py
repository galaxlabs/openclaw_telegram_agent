import os
import sqlite3
import asyncio
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Bot
from runtime_support import (
    build_dedupe_signature,
    ensure_items_schema,
    find_existing_item_by_signature,
    get_db_path,
    parse_post_limit,
)
from publish_support import (
    get_publish_config,
    is_item_fully_processed,
    make_post,
    publish_to_website,
)

load_dotenv()

DB = get_db_path("agent.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_unprocessed(limit: int):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute("""
        SELECT
            id,
            title,
            url,
            note,
            source_chat_id,
            source_message_id,
            source_date_utc,
            website_published,
            telegram_published,
            source_deleted,
            dedupe_signature,
            duplicate_of_item_id
        FROM items
        WHERE processed=0 AND url IS NOT NULL
        ORDER BY (source_chat_id=0) ASC, id ASC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def update_item_status(item_id: int, **fields):
    if not fields:
        return
    con = sqlite3.connect(DB)
    cur = con.cursor()
    assignments = ", ".join(f"{col}=?" for col in fields)
    values = list(fields.values()) + [item_id]
    cur.execute(f"UPDATE items SET {assignments} WHERE id=?", values)
    con.commit()
    con.close()


async def mark_duplicate_item(
    *,
    bot: Bot | None,
    item: dict,
    item_id: int,
    signature: str,
    duplicate_of_item_id: int,
    delete_required: bool,
):
    fields = {
        "dedupe_signature": signature,
        "duplicate_of_item_id": duplicate_of_item_id,
        "processed": 1,
        "processed_at_utc": now_iso(),
        "publish_error": "duplicate_skipped",
    }

    if delete_required and not item.get("source_deleted") and bot is not None:
        await bot.delete_message(
            chat_id=int(item["source_chat_id"]),
            message_id=int(item["source_message_id"]),
        )
        fields["source_deleted"] = 1
        fields["source_deleted_at_utc"] = now_iso()
        item["source_deleted"] = 1
        print(
            "DELETED duplicate source message",
            item["source_message_id"],
            "from",
            item["source_chat_id"],
        )

    update_item_status(item_id, **fields)
    print("SKIPPED DUPLICATE item", item_id, "duplicate_of", duplicate_of_item_id)

async def main(limit: int = 5):
    ensure_items_schema(DB)
    cfg = get_publish_config()
    if not cfg["website_enabled"] and not cfg["telegram_enabled"]:
        raise SystemExit(
            "No publish target configured. Set TELEGRAM_TARGET_CHAT_ID or WEBSITE_PUBLISH_URL."
        )

    rows = fetch_unprocessed(limit)
    if not rows:
        print("No unprocessed items to post.")
        return

    bot = None
    if cfg["telegram_enabled"] or cfg["delete_enabled"]:
        bot = Bot(cfg["bot_token"])

    completed = 0
    published_signatures: dict[str, int] = {}

    for item in rows:
        item_id = item["id"]
        text = make_post(item["title"], item["url"], item["note"])
        signature = item.get("dedupe_signature") or build_dedupe_signature(
            item.get("title"),
            item.get("url"),
            item.get("note"),
        )
        try:
            delete_required = (
                cfg["delete_enabled"]
                and str(item["source_chat_id"]) != "0"
                and int(item["source_message_id"]) > 0
            )

            duplicate_of_item_id = published_signatures.get(signature) or find_existing_item_by_signature(
                DB,
                signature,
                exclude_item_id=item_id,
                require_published=True,
            )
            if duplicate_of_item_id:
                await mark_duplicate_item(
                    bot=bot,
                    item=item,
                    item_id=item_id,
                    signature=signature,
                    duplicate_of_item_id=duplicate_of_item_id,
                    delete_required=delete_required,
                )
                continue

            if item.get("dedupe_signature") != signature:
                update_item_status(item_id, dedupe_signature=signature)

            if cfg["website_enabled"] and not item.get("website_published"):
                publish_to_website(item, text)
                update_item_status(
                    item_id,
                    website_published=1,
                    website_published_at_utc=now_iso(),
                    dedupe_signature=signature,
                    publish_error=None,
                )
                item["website_published"] = 1
                print("WEBSITE PUBLISHED item", item_id)

            if cfg["telegram_enabled"] and not item.get("telegram_published"):
                await bot.send_message(
                    chat_id=cfg["target_chat_id"],
                    text=text,
                    disable_web_page_preview=False,
                )
                update_item_status(
                    item_id,
                    telegram_published=1,
                    telegram_published_at_utc=now_iso(),
                    dedupe_signature=signature,
                    publish_error=None,
                )
                item["telegram_published"] = 1
                print("TELEGRAM POSTED item", item_id)

            if delete_required and not item.get("source_deleted"):
                await bot.delete_message(
                    chat_id=int(item["source_chat_id"]),
                    message_id=int(item["source_message_id"]),
                )
                update_item_status(
                    item_id,
                    source_deleted=1,
                    source_deleted_at_utc=now_iso(),
                    dedupe_signature=signature,
                    publish_error=None,
                )
                item["source_deleted"] = 1
                print(
                    "DELETED source message",
                    item["source_message_id"],
                    "from",
                    item["source_chat_id"],
                )

            if is_item_fully_processed(
                item=item,
                website_enabled=cfg["website_enabled"],
                telegram_enabled=cfg["telegram_enabled"],
                delete_enabled=delete_required,
            ):
                update_item_status(
                    item_id,
                    processed=1,
                    processed_at_utc=now_iso(),
                    dedupe_signature=signature,
                    publish_error=None,
                )
                completed += 1
                published_signatures[signature] = item_id
                print("MARKED PROCESSED item", item_id)
        except Exception as e:
            err = str(e)[:1000]
            update_item_status(item_id, publish_error=err)
            print("WARN: item failed", item_id, err)

    print("Marked processed:", completed)

if __name__ == "__main__":
    asyncio.run(main(limit=parse_post_limit(sys.argv[1:])))
