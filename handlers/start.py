from aiogram import Router, types
from aiogram.filters import Command
from database import get_user, create_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    if not get_user(tg_id):
        create_user(tg_id)
    
    await message.answer(
        "🚀 Добро пожаловать!\n\n"
        "📤 Отправьте ссылку на оплату (QR-код), чтобы начать."
    )