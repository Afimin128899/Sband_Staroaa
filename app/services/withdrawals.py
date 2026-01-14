from sqlalchemy import select
from app.database import Session
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.services.transactions import add_transaction

async def has_pending(user_id: int) -> bool:
    async with Session() as s:
        q = await s.scalar(
            select(Withdrawal)
            .where(Withdrawal.user_id == user_id)
            .where(Withdrawal.status == "pending")
        )
        return q is not None

async def create_withdrawal(user_id: int, amount: int):
    async with Session() as s:
        async with s.begin():
            user = await s.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )

            if user.balance - user.locked_balance < amount:
                raise ValueError

            user.locked_balance += amount
            s.add(Withdrawal(user_id=user_id, amount=amount))

async def complete_withdrawal(withdrawal_id: int):
    async with Session() as s:
        async with s.begin():
            w = await s.scalar(
                select(Withdrawal)
                .where(Withdrawal.id == withdrawal_id)
                .with_for_update()
            )
            user = await s.get(User, w.user_id)

            user.balance -= w.amount
            user.locked_balance -= w.amount
            w.status = "completed"

    await add_transaction(w.user_id, -w.amount, "withdraw")

async def reject_withdrawal(withdrawal_id: int):
    async with Session() as s:
        async with s.begin():
            w = await s.get(Withdrawal, withdrawal_id)
            user = await s.get(User, w.user_id)

            user.locked_balance -= w.amount
            w.status = "rejected"

