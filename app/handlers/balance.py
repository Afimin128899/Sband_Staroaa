from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.database import Session
from app.models.user import User

router = Router()

@router.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    async with Session() as s:
        user = await s.get(User, call.from_user.id)
        available = user.balance - user.locked_balance
        await call.message.answer(
            f"Баланс: {user.balance/4:.2f} ⭐\n"
            f"Заблокировано: {user.locked_balance/4:.2f} ⭐\n"
            f"Доступно: {available/4:.2f} ⭐"
        )
