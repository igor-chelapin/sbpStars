from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_user, create_user, update_user_role

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    user = get_user(tg_id)
    
    if not user:
        create_user(tg_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Я покупатель", callback_data="role_buyer")],
        [InlineKeyboardButton(text="💼 Я агент", callback_data="role_agent")],
        [InlineKeyboardButton(text="💰 аланс", callback_data="balance")],
    ])
    
    await message.answer(
        "🚀 обро пожаловать в StarsPayBot!\n\n"
        "урс: 1 Star = 1.5\n"
        "омиссия: 5%\n\n"
        "ыберите роль:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[1]
    tg_id = callback.from_user.id
    
    update_user_role(tg_id, role)
    await callback.answer(f"✅ оль изменена")
    
    if role == "buyer":
        text = "🛒 ы покупатель. тправьте ссылку на оплату, чтобы начать."
    else:
        text = "💼 ы агент. жидайте заказы в закрытом канале."
    
    await callback.message.answer(text)
    await callback.message.delete()
