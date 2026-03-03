from aiogram import Router, types
from aiogram.filters import Command
from database import get_user

router = Router()

@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        await message.answer(f"💰 Виртуальный баланс: {user[2]} Stars")
    else:
        await message.answer("❌ Сначала /start")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📤 Отправь ссылку на оплату → введи сумму → оплати Stars\n"
        "Агенты выполнят заказ."
    )