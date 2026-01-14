from sqlalchemy import Integer, BigInteger, String
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)
