from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.services.withdrawals import create_withdrawal, has_pending
from app.config import WITHDRAW_MIN_UNITS

router = Router()

@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    if await has_pending(call.from_user.id):
        await call.answer("⏳ Уже есть заявка", show_alert=True)
        return

    try:
        await create_withdrawal(call.from_user.id, WITHDRAW_MIN_UNITS)
        await call.message.answer("⏳ Заявка создана")
    except:
        await call.message.answer("❌ Недостаточно средств")

