import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import start, common

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(bot, storage=MemoryStorage())
    
    dp.include_router(start.router)
    dp.include_router(common.router)
    
    await bot.set_my_commands([
        BotCommand(command="start", description="запустить бота"),
        BotCommand(command="balance", description="мой баланс"),
        BotCommand(command="help", description="помощь"),
    ])
    
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
