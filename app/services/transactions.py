from app.database import Session
from app.models.transaction import Transaction

async def add_transaction(user_id: int, amount: int, type_: str):
    async with Session() as s:
        async with s.begin():
            s.add(Transaction(
                user_id=user_id,
                amount=amount,
                type=type_
            ))
