from aiogram import Router, types
from aiogram.filters import Command
from database import get_user

router = Router()

@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user = get_user(message.from_user.id)
    balance = user[3] if user else 0
    await message.answer(f"💰 аш баланс: {balance} Stars")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ помощь\n\n"
        "1. выберите роль (/start)\n"
        "2. покупатель: отправьте ссылку на оплату\n"
        "3. агент: выполняйте заказы из канала"
    )
