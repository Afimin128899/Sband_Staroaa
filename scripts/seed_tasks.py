import asyncio
from app.database import Session
from app.models.task import Task

async def main():
    async with Session() as s:
        async with s.begin():
            s.add_all([
                Task(title="Подписка на канал", reward=1),
                Task(title="Вступить в чат", reward=1)
            ])

asyncio.run(main())
