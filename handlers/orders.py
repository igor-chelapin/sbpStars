from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re

from database import get_user, update_user_balance, create_order
from config import STARS_RATE, BOT_COMMISSION

router = Router()

class OrderStates(StatesGroup):
    waiting_for_amount = State()

@router.message(lambda message: re.match(r'https?://', message.text))
async def handle_qr_link(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    
    if not user or user[2] != 'buyer':
        await message.answer("❌ Только покупатели могут создавать заказы")
        return
    
    await state.update_data(qr_link=message.text.strip())
    await message.answer("Введите сумму в рублях:")
    await state.set_state(OrderStates.waiting_for_amount)

@router.message(OrderStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите число")
        return
    
    rub_amount = int(message.text)
    data = await state.get_data()
    qr_link = data.get('qr_link')
    
    stars_needed = rub_amount / STARS_RATE
    commission = stars_needed * BOT_COMMISSION
    total_stars = int(stars_needed + commission) + 1
    
    user = get_user(message.from_user.id)
    if user[3] < total_stars:
        await message.answer(f"❌ Недостаточно Stars. Баланс: {user[3]}, нужно: {total_stars}")
        await state.clear()
        return
    
    update_user_balance(message.from_user.id, -total_stars)
    
    order_number = create_order(
        buyer_id=message.from_user.id,
        qr_link=qr_link,
        rub_amount=rub_amount,
        stars_amount=total_stars,
        stars_for_agent=int(stars_needed)
    )
    
    await message.answer(
        f"✅ Заказ {order_number} создан!\n"
        f"Сумма: {rub_amount}₽\n"
        f"Списано Stars: {total_stars}\n"
        f"Агент получит: {int(stars_needed)} Stars\n\n"
        f"Ищем агента..."
    )
    
    await state.clear()