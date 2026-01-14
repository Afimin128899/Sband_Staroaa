from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from app.database import Session
from app.models.user import User
from app.keyboards.inline import main_menu
from app.services.referrals import reward_referrer

router = Router()

@router.message(CommandStart())
async def start(m: Message):
    args = m.text.split()
    ref = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    async with Session() as s:
        if not await s.get(User, m.from_user.id):
            s.add(User(
                id=m.from_user.id,
                username=m.from_user.username,
                first_name=m.from_user.first_name,
                referrer_id=ref
            ))
            await s.commit()
            if ref:
                await reward_referrer(ref)

    await m.answer("", reply_markup=main_menu())

