import os
import asyncio
from telegram import Bot

async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_TARGET_CHAT_ID")

    if not token or not chat_id:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_TARGET_CHAT_ID in environment.")

    bot = Bot(token)
    await bot.send_message(chat_id=chat_id, text="✅ OpenClaw Telegram Agent: test message (async ok)")
    print("sent")

if __name__ == "__main__":
    asyncio.run(main())
