from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    locked_balance: Mapped[int] = mapped_column(Integer, default=0)
