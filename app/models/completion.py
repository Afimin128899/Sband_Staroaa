from sqlalchemy import Integer, BigInteger, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base

class TaskCompletion(Base):
    __tablename__ = "task_completions"
    __table_args__ = (UniqueConstraint("user_id", "task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    task_id: Mapped[int] = mapped_column(Integer)
