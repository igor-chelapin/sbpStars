from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

from database import get_user, update_user_balance, create_order, get_order, update_order_status, save_proof_file
from config import STARS_RATE, BOT_COMMISSION, CHANNEL_ID, ADMIN_IDS

router = Router()

class OrderStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_proof = State()

# ----------------- ПОКУПАТЕЛЬ -----------------

@router.message(lambda message: re.match(r'https?://', message.text))
async def handle_qr_link(message: types.Message, state: FSMContext):
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
    if user[2] < total_stars:
        await message.answer(f"❌ Недостаточно Stars. Баланс: {user[2]}, нужно: {total_stars}")
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
    
    agent_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Взять заказ", callback_data=f"take_{order_number}")]
    ])
    
    await message.bot.send_message(
        chat_id=CHANNEL_ID,
        text=(
            f"🆕 **Новый заказ**\n"
            f"Номер: `{order_number}`\n"
            f"Сумма: {rub_amount}₽\n"
            f"Награда: {int(stars_needed)} Stars\n"
            f"[Ссылка для оплаты]({qr_link})"
        ),
        parse_mode="Markdown",
        reply_markup=agent_keyboard
    )
    
    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Получил товар", callback_data=f"confirm_{order_number}")]
    ])
    
    await message.answer(
        f"✅ Заказ {order_number} создан!\n"
        f"Сумма: {rub_amount}₽\n"
        f"Списано Stars: {total_stars}\n\n"
        f"Задание отправлено агентам в канал.\n"
        f"После получения товара нажмите кнопку:",
        reply_markup=buyer_keyboard
    )
    
    await state.clear()

# ----------------- АГЕНТ -----------------

@router.callback_query(lambda c: c.data.startswith('take_'))
async def take_order(callback: types.CallbackQuery):
    order_number = callback.data.split('_')[1]
    order = get_order(order_number)
    
    if not order:
        await callback.answer("❌ Заказ не найден")
        return
    
    if order[7] != 'waiting_agent':
        await callback.answer("❌ Заказ уже взят")
        return
    
    update_order_status(order_number, 'taken', agent_id=callback.from_user.id)
    
    agent_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"paid_{order_number}")]
    ])
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Заказ взят агентом"
    )
    
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            f"✅ Вы взяли заказ {order_number}\n\n"
            f"Сумма: {order[5]}₽\n"
            f"Ссылка: {order[4]}\n\n"
            f"После оплаты нажмите кнопку:"
        ),
        reply_markup=agent_keyboard
    )
    
    await callback.answer("✅ Заказ закреплён")

@router.callback_query(lambda c: c.data.startswith('paid_'))
async def agent_paid(callback: types.CallbackQuery, state: FSMContext):
    order_number = callback.data.split('_')[1]
    
    await state.update_data(order_number=order_number)
    await callback.message.answer("📸 Отправьте скриншот или фото чека об оплате:")
    await state.set_state(OrderStates.waiting_for_proof)

@router.message(OrderStates.waiting_for_proof, lambda message: message.photo)
async def handle_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_number = data.get('order_number')
    order = get_order(order_number)
    
    if not order:
        await message.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    file_id = message.photo[-1].file_id
    save_proof_file(order_number, file_id)
    update_order_status(order_number, 'paid_by_agent')
    
    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Получил товар", callback_data=f"confirm_{order_number}")]
    ])
    
    await message.bot.send_photo(
        chat_id=order[3],
        photo=file_id,
        caption=(
            f"📸 Агент оплатил заказ {order_number}\n"
            f"Сумма: {order[5]}₽\n\n"
            f"Подтвердите получение товара:"
        ),
        reply_markup=buyer_keyboard
    )
    
    await message.answer("✅ Подтверждение отправлено покупателю")
    await state.clear()

# ----------------- ПОКУПАТЕЛЬ (ПОДТВЕРЖДЕНИЕ) -----------------

@router.callback_query(lambda c: c.data.startswith('confirm_'))
async def confirm_order(callback: types.CallbackQuery):
    order_number = callback.data.split('_')[1]
    order = get_order(order_number)
    
    if not order:
        await callback.answer("❌ Заказ не найден")
        return
    
    if order[7] != 'paid_by_agent':
        await callback.answer("❌ Заказ ещё не оплачен агентом")
        return
    
    update_user_balance(order[8], order[6])
    update_order_status(order_number, 'completed')
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Товар получен, спасибо!"
    )
    
    await callback.bot.send_message(
        chat_id=order[8],
        text=f"✅ Заказ {order_number} завершен. Stars начислены."
    )
    
    await callback.answer("✅ Спасибо!")

# ----------------- АДМИН ПАНЕЛЬ -----------------

@router.message(lambda message: message.text == "/admin")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    from database import get_all_orders
    
    orders = get_all_orders(limit=20)
    if not orders:
        await message.answer("📭 Нет заказов")
        return
    
    text = "📊 **Последние 20 заказов:**\n\n"
    for order in orders:
        status_emoji = {
            'waiting_agent': '🟡',
            'taken': '🔵',
            'paid_by_agent': '🟠',
            'completed': '✅',
            'dispute': '⚠️'
        }.get(order[7], '⚪')
        
        text += (
            f"{status_emoji} `{order[2]}`\n"
            f"   Сумма: {order[5]}₽\n"
            f"   Статус: {order[7]}\n"
            f"   Покупатель: {order[3]}\n"
        )
        if order[8]:
            text += f"   Агент: {order[8]}\n"
        if order[10]:
            text += f"   📸 Есть скрин\n"
        text += "\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(lambda message: message.text.startswith("/order "))
async def admin_order_detail(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    order_number = message.text.split()[1]
    order = get_order(order_number)
    
    if not order:
        await message.answer("❌ Заказ не найден")
        return
    
    text = (
        f"📦 **Заказ {order[2]}**\n\n"
        f"Статус: {order[7]}\n"
        f"Сумма: {order[5]}₽\n"
        f"Stars: {order[6]} (агенту: {order[6]})\n"
        f"Покупатель: {order[3]}\n"
        f"Агент: {order[8] or 'не назначен'}\n"
        f"Ссылка: {order[4]}\n"
        f"Создан: {order[9]}\n"
    )
    
    await message.answer(text, parse_mode="Markdown")
    
    if order[10]:
        await message.bot.send_photo(
            chat_id=message.from_user.id,
            photo=order[10],
            caption="📸 Скриншот оплаты от агента"
        )