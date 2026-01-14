
from app.database import Session
from app.models.user import User
from app.services.transactions import add_transaction

TASK_REWARD = 0.25
REFERRAL_REWARD = 2

async def add_reward(user_id: int, amount: int, type_: str):
    async with Session() as s:
        async with s.begin():
            user = await s.get(User, user_id)
            user.balance += amount
    await add_transaction(user_id, amount, type_)
