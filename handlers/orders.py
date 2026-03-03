from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import re
import asyncio

from database import get_user, update_virtual_balance, create_order, get_order, update_order_status, save_proof_file
from config import STARS_RATE, BOT_COMMISSION, CHANNEL_ID, ADMIN_IDS, PROVIDER_TOKEN

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
    
    # Вместо проверки баланса — сразу создаём инвойс на оплату
    prices = [LabeledPrice(label="Оплата заказа", amount=total_stars * 100)]
    
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Оплата заказа",
        description=f"Сумма: {rub_amount}₽",
        payload=f"order_{qr_link}_{rub_amount}_{stars_needed}_{total_stars}",
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=prices
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

# ----------------- ДАЛЬШЕ ВСЯ ЛОГИКА АГЕНТОВ (take_, paid_, confirm_, dispute_) ОСТАЁТСЯ БЕЗ ИЗМЕНЕНИЙ ---------