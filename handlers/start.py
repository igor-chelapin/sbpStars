from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database import get_user, create_user

router = Router()

# Кнопки главного меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Оплатить покупку")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="❓ Помощь")]
    ],
    resize_keyboard=True
)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    if not get_user(tg_id):
        create_user(tg_id)
    
    await message.answer(
        "🚀 Добро пожаловать!\n\n"
        "Нажми **💳 Оплатить покупку**, чтобы начать.\n"
        "Или отправь ссылку на оплату напрямую.",
        reply_markup=main_keyboard
    )

@router.message(lambda message: message.text == "💳 Оплатить покупку")
async def button_pay(message: types.Message):
    await message.answer("📤 Отправьте ссылку на оплату (QR-код):")

@router.message(lambda message: message.text == "💰 Баланс")
async def button_balance(message: types.Message):
    from database import get_user
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0
    await message.answer(f"💰 Ваш виртуальный баланс: {balance} Stars")

@router.message(lambda message: message.text == "❓ Помощь")
async def button_help(message: types.Message):
    await message.answer(
        "🔹 Отправь ссылку на оплату\n"
        "🔹 Введи сумму в рублях\n"
        "🔹 Оплати Stars\n"
        "🔹 Агент выполнит заказ"
    )