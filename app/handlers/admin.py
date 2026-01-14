from aiogram import Router, F
from aiogram.types import Message
from app.services.withdrawals import complete_withdrawal, reject_withdrawal

ADMIN_IDS = {123456789}

router = Router()

@router.message(F.text.startswith("/approve"))
async def approve(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    wid = int(m.text.split()[1])
    await complete_withdrawal(wid)
    await m.answer("✅")

@router.message(F.text.startswith("/reject"))
async def reject(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    wid = int(m.text.split()[1])
    await reject_withdrawal(wid)
    await m.answer("❌")
