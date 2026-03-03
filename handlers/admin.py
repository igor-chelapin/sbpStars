from aiogram import Router, types
from aiogram.filters import Command
from database import get_all_users, get_all_orders
from config import ADMIN_IDS

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    orders = get_all_orders(10)
    users = get_all_users()
    
    text = "📊 **Статистика**\n\n"
    text += f"👥 Всего пользователей: {len(users)}\n"
    text += f"📦 Заказов: {len(orders)}\n\n"
    text += "**Последние заказы:**\n"
    
    for o in orders[:5]:
        text += f"• `{o[2]}` {o[5]}₽ — {o[7]}\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("balances"))
async def show_balances(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    users = get_all_users()
    text = "💰 **Балансы (виртуальные | реальные)**\n\n"
    for u in users:
        text += f"`{u[0]}`: {u[1]} | {u[2]}\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("pay"))
async def pay_agent(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ /pay агент_айди сумма")
        return
    
    try:
        agent_id = int(args[1])
        amount = int(args[2])
        from database import update_real_balance
        update_real_balance(agent_id, amount)
        await message.answer(f"✅ Начислено {amount} реальных Stars агенту {agent_id}")
    except:
        await message.answer("❌ Ошибка")