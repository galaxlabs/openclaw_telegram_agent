#!/usr/bin/env python3
import os
import json
import sqlite3
import subprocess
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from runtime_support import ensure_items_schema, ensure_parent_dir, get_control_path, get_db_path

load_dotenv()

BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = get_db_path("agent.db")
CONTROL_PATH = get_control_path("control.json")

if not BOT_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_control():
    if not os.path.exists(CONTROL_PATH):
        return {"paused": False, "post_limit": 5}
    with open(CONTROL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_control(data):
    ensure_parent_dir(CONTROL_PATH)
    with open(CONTROL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_panel_text():
    c = load_control()
    status = "PAUSED ⏸" if c.get("paused") else "RUNNING ▶️"
    limit = c.get("post_limit", 5)
    return f"OpenClaw Control Panel\nStatus: {status}\nPost limit: {limit}\nTime(UTC): {now_iso()}"

def build_panel_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume"),
        ],
        [
            InlineKeyboardButton("🚀 Post now", callback_data="postnow"),
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="panel"),
        ]
    ])

def db_stats():
    # very safe stats: count unprocessed + total
    ensure_items_schema(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Find which column name exists
    cur.execute("PRAGMA table_info(items)")
    cols = {r[1] for r in cur.fetchall()}

    processed_col = "processed" if "processed" in cols else None

    total = 0
    unprocessed = 0

    cur.execute("SELECT COUNT(*) FROM items")
    total = cur.fetchone()[0]

    if processed_col:
        cur.execute("SELECT COUNT(*) FROM items WHERE processed = 0")
        unprocessed = cur.fetchone()[0]

    conn.close()
    return total, unprocessed

def run_post_once():
    """
    Runs post_organized.py once.
    If your post_organized.py supports --limit, we use control.json post_limit.
    """
    c = load_control()
    if c.get("paused"):
        return "Posting is paused. Nothing posted."

    limit = int(c.get("post_limit", 5))

    cmd = ["bash", "-lc", f"cd '{os.getcwd()}' && source .venv/bin/activate && python post_organized.py --limit {limit}"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()

    if p.returncode != 0:
        return f"ERROR running post_organized.py\n{err or out or 'unknown error'}"

    return out or "Done (no output)."

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_panel_text(), reply_markup=build_panel_keyboard())

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = load_control()
    c["paused"] = True
    save_control(c)
    await update.message.reply_text("Paused ✅")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = load_control()
    c["paused"] = False
    save_control(c)
    await update.message.reply_text("Resumed ✅")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, unprocessed = db_stats()
    c = load_control()
    status = "PAUSED ⏸" if c.get("paused") else "RUNNING ▶️"
    await update.message.reply_text(f"Stats\nStatus: {status}\nTotal items: {total}\nUnprocessed: {unprocessed}")

async def cmd_postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = run_post_once()
    # Keep it short to avoid Telegram message limits
    if len(msg) > 3500:
        msg = msg[:3500] + "\n...(trimmed)"
    await update.message.reply_text(msg)

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data

    if data == "panel":
        await q.edit_message_text(build_panel_text(), reply_markup=build_panel_keyboard())
        return

    if data == "pause":
        c = load_control()
        c["paused"] = True
        save_control(c)
        await q.edit_message_text(build_panel_text(), reply_markup=build_panel_keyboard())
        return

    if data == "resume":
        c = load_control()
        c["paused"] = False
        save_control(c)
        await q.edit_message_text(build_panel_text(), reply_markup=build_panel_keyboard())
        return

    if data == "stats":
        total, unprocessed = db_stats()
        c = load_control()
        status = "PAUSED ⏸" if c.get("paused") else "RUNNING ▶️"
        text = f"{build_panel_text()}\n\nStats:\nTotal items: {total}\nUnprocessed: {unprocessed}"
        await q.edit_message_text(text, reply_markup=build_panel_keyboard())
        return

    if data == "postnow":
        result = run_post_once()
        if len(result) > 3000:
            result = result[:3000] + "\n...(trimmed)"
        text = f"{build_panel_text()}\n\nPost result:\n{result}"
        await q.edit_message_text(text, reply_markup=build_panel_keyboard())
        return

def main():
    ensure_items_schema(DB_PATH)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("postnow", cmd_postnow))

    app.add_handler(CallbackQueryHandler(on_button))

    print("Control bot started. Use /panel in your group.")
    app.run_polling()

if __name__ == "__main__":
    main()
