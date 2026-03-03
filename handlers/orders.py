from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import re
import asyncio

from database import get_user, update_virtual_balance, create_order, get_order, update_order_status, save_proof_file
from config import STARS_RATE, BOT_COMMISSION, CHANNEL_ID, ADMIN_IDS

router = Router()

class OrderStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_proof = State()

# ----------------- ПОКУПАТЕЛЬ -----------------

@router.message(lambda message: re.match(r'https?://', message.text))
async def handle_qr_link(message: types.Message, state: FSMContext):
    await state.update_data(qr_link=message.text.strip())
    await message.answer("Введите сумму в рублях, которую нужно оплатить:")
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
    
    await state.update_data(
        rub_amount=rub_amount,
        qr_link=qr_link,
        stars_needed=stars_needed,
        total_stars=total_stars
    )
    
    pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💎 Оплатить {total_stars} Stars", callback_data="pay_stars")]
    ])
    
    await message.answer(
        f"💰 К оплате:\n"
        f"Сумма: {rub_amount}₽\n"
        f"Курс: 1 Star = {STARS_RATE}₽\n"
        f"Комиссия: {BOT_COMMISSION*100}%\n\n"
        f"Итого Stars: {total_stars}",
        reply_markup=pay_keyboard
    )

@router.callback_query(lambda c: c.data == "pay_stars")
async def pay_stars(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rub_amount = data.get('rub_amount')
    qr_link = data.get('qr_link')
    stars_needed = data.get('stars_needed')
    total_stars = data.get('total_stars')
    
    # Для XTR сумма указывается 1:1, без умножения
    prices = [LabeledPrice(label="Оплата заказа", amount=total_stars)]
    
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Оплата заказа",
        description=f"Сумма: {rub_amount}₽",
        payload=f"order_{qr_link}_{rub_amount}_{stars_needed}_{total_stars}",
        currency="XTR",  # Волшебная валюта Stars
        prices=prices
        # provider_token НЕ НУЖЕН для XTR
    )
    
    await callback.message.delete()
    await state.clear()

@router.message(lambda message: message.successful_payment)
async def successful_payment(message: types.Message):
    # Парсим payload
    payload = message.successful_payment.invoice_payload
    parts = payload.split('_', 4)
    
    if len(parts) == 5:
        _, qr_link, rub_amount, stars_needed, total_stars = parts
        rub_amount = int(rub_amount)
        stars_needed = float(stars_needed)
        total_stars = int(total_stars)
        
        # Зачисляем виртуальные Stars на баланс пользователя
        update_virtual_balance(message.from_user.id, total_stars)
        
        # Создаём заказ
        order_number = create_order(
            buyer_id=message.from_user.id,
            qr_link=qr_link,
            rub_amount=rub_amount,
            stars_amount=total_stars,
            stars_for_agent=int(stars_needed)
        )
        
        # Отправляем задание в канал агентам
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
        
        await message.answer(
            f"✅ Оплата прошла успешно!\n"
            f"На ваш виртуальный баланс зачислено {total_stars} Stars.\n"
            f"Заказ {order_number} создан и отправлен агентам."
        )

# ----------------- АГЕНТ: ВЗЯТЬ ЗАКАЗ -----------------

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
    
    # Назначаем агента
    update_order_status(order_number, 'taken', agent_id=callback.from_user.id)
    
    # Отправляем агенту в личку ссылку для оплаты
    agent_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"paid_{order_number}")]
    ])
    
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            f"✅ Вы взяли заказ {order_number}\n\n"
            f"Сумма к оплате: {order[5]}₽\n"
            f"Ссылка для оплаты (СБП):\n{order[4]}\n\n"
            f"⚠️ У вас 2 минуты на оплату!\n"
            f"После оплаты нажмите кнопку:"
        ),
        reply_markup=agent_keyboard
    )
    
    # Обновляем сообщение в канале
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Заказ взят агентом"
    )
    
    # Запускаем таймер на 2 минуты
    asyncio.create_task(agent_timeout(order_number, callback.from_user.id, callback.message.chat.id, callback.message.message_id))
    
    await callback.answer("✅ Заказ закреплён")

# ----------------- ТАЙМЕР АГЕНТА (2 МИНУТЫ) -----------------

async def agent_timeout(order_number, agent_id, channel_id, message_id):
    await asyncio.sleep(120)  # 2 минуты
    
    order = get_order(order_number)
    if order and order[7] == 'taken' and order[8] == agent_id:
        # Агент не оплатил — возвращаем заказ в канал
        update_order_status(order_number, 'waiting_agent', agent_id=None)
        
        # Создаём новую клавиатуру для канала
        agent_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Взять заказ", callback_data=f"take_{order_number}")]
        ])
        
        # Пробуем отредактировать сообщение в канале
        try:
            bot = router.bot if hasattr(router, 'bot') else None
            if bot:
                await bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=message_id,
                    text=(
                        f"🆕 **Новый заказ**\n"
                        f"Номер: `{order_number}`\n"
                        f"Сумма: {order[5]}₽\n"
                        f"Награда: {order[6]} Stars\n"
                        f"[Ссылка для оплаты]({order[4]})\n\n"
                        f"⚠️ Предыдущий агент не оплатил вовремя"
                    ),
                    parse_mode="Markdown",
                    reply_markup=agent_keyboard
                )
        except:
            pass

# ----------------- АГЕНТ: ПОДТВЕРЖДЕНИЕ ОПЛАТЫ -----------------

@router.callback_query(lambda c: c.data.startswith('paid_'))
async def agent_paid(callback: types.CallbackQuery, state: FSMContext):
    order_number = callback.data.split('_')[1]
    
    await state.update_data(order_number=order_number)
    await callback.message.answer("📸 Отправьте скриншот или фото чека об оплате:")
    await state.set_state(OrderStates.waiting_for_proof)

# ----------------- АГЕНТ: ОТПРАВКА СКРИНА -----------------

@router.message(OrderStates.waiting_for_proof, lambda message: message.photo)
async def handle_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_number = data.get('order_number')
    order = get_order(order_number)
    
    if not order:
        await message.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    # Сохраняем скрин
    file_id = message.photo[-1].file_id
    save_proof_file(order_number, file_id)
    update_order_status(order_number, 'paid_by_agent')
    
    # Кнопки для покупателя
    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, товар получил", callback_data=f"confirm_{order_number}"),
            InlineKeyboardButton(text="❌ Нет, товар не пришёл", callback_data=f"dispute_{order_number}")
        ]
    ])
    
    # Отправляем скрин покупателю
    await message.bot.send_photo(
        chat_id=order[3],  # buyer_id
        photo=file_id,
        caption=(
            f"📸 Агент оплатил заказ {order_number}\n"
            f"Сумма: {order[5]}₽\n\n"
            f"Товар получен? У вас 15 минут на ответ."
        ),
        reply_markup=buyer_keyboard
    )
    
    await message.answer("✅ Подтверждение отправлено покупателю")
    
    # Запускаем таймер на 15 минут
    asyncio.create_task(buyer_timeout(order_number, message.bot, order[3], order[8]))
    
    await state.clear()

# ----------------- ТАЙМЕР ПОКУПАТЕЛЯ (15 МИНУТ) -----------------

async def buyer_timeout(order_number, bot, buyer_id, agent_id):
    await asyncio.sleep(900)  # 15 минут
    
    order = get_order(order_number)
    if order and order[7] == 'paid_by_agent':
        # Покупатель не ответил — Stars уходят агенту
        update_virtual_balance(agent_id, order[6])  # stars_for_agent
        update_order_status(order_number, 'completed')
        
        await bot.send_message(
            chat_id=agent_id,
            text=f"✅ Заказ {order_number} завершен автоматически. Stars начислены."
        )
        
        await bot.send_message(
            chat_id=buyer_id,
            text=f"⚠️ Заказ {order_number} автоматически завершен. Stars ушли агенту."
        )

# ----------------- ПОКУПАТЕЛЬ: ПОДТВЕРЖДЕНИЕ -----------------

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
    
    # Начисляем виртуальные Stars агенту
    update_virtual_balance(order[8], order[6])  # agent_id, stars_for_agent
    update_order_status(order_number, 'completed')
    
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Товар получен, спасибо! Виртуальные Stars ушли агенту."
    )
    
    await callback.bot.send_message(
        chat_id=order[8],
        text=f"✅ Заказ {order_number} завершен. Виртуальные Stars начислены."
    )
    
    await callback.answer("✅ Спасибо!")

# ----------------- ПОКУПАТЕЛЬ: ДИСПУТ -----------------

@router.callback_query(lambda c: c.data.startswith('dispute_'))
async def dispute_order(callback: types.CallbackQuery):
    order_number = callback.data.split('_')[1]
    order = get_order(order_number)
    
    if not order:
        await callback.answer("❌ Заказ не найден")
        return
    
    update_order_status(order_number, 'dispute')
    
    await callback.message.edit_text(
        callback.message.text + "\n\n⚠️ Открыт спор. Администратор скоро подключится."
    )
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"⚠️ **Спор по заказу {order_number}**\n"
                    f"Покупатель утверждает, что не получил товар.\n"
                    f"Посмотреть: /order {order_number}"
                ),
                parse_mode="Markdown"
            )
        except:
            pass
    
    await callback.answer("✅ Спор открыт")