from sqlalchemy import Integer, String
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    reward: Mapped[int] = mapped_column(Integer, default=1)
