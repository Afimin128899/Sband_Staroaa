import asyncio
from aiogram import Bot
from app.config import BOT_TOKEN
from app.dispatcher import dp

async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
