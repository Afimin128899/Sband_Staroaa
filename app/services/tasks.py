from sqlalchemy import select
from app.database import Session
from app.models.task import Task
from app.models.completion import TaskCompletion

async def get_tasks():
    async with Session() as s:
        return (await s.scalars(select(Task))).all()

async def is_completed(user_id: int, task_id: int) -> bool:
    async with Session() as s:
        q = await s.scalar(
            select(TaskCompletion)
            .where(TaskCompletion.user_id == user_id)
            .where(TaskCompletion.task_id == task_id)
        )
        return q is not None

async def mark_completed(user_id: int, task_id: int):
    async with Session() as s:
        async with s.begin():
            s.add(TaskCompletion(user_id=user_id, task_id=task_id))
