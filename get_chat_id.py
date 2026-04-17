import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN is not set. Put it in .env and export it before running.")

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    print(f"chat_id={chat.id} title={getattr(chat, 'title', None)} type={chat.type}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handler))
    print("Listening... Now send a message in your TARGET Telegram group.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
