from aiogram import Router, types
from aiogram.filters import Command
from database import get_user

router = Router()

@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0  # stars_balance = user[2]
    await message.answer(f"💰 Ваш баланс: {balance} Stars")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ Помощь\n\n"
        "1. Отправьте ссылку на оплату\n"
        "2. Введите сумму в рублях\n"
        "3. Оплатите Stars\n"
        "4. платеж будет обработан в течение 5 минут "
    )