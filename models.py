from typing import Optional
from sqlalchemy import String, Integer
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

class Base(DeclarativeBase):
    pass

class Node(Base):
    __tablename__ = "node"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(255))
    long_name: Mapped[Optional[str]] = mapped_column(String(255))
    macaddr: Mapped[Optional[str]] = mapped_column(String(17))
    hw_model: Mapped[Optional[str]] = mapped_column(Integer)
    public_key: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[float]] = mapped_column(Integer)
    longitude: Mapped[Optional[float]] = mapped_column(Integer)
    altitude: Mapped[Optional[float]] = mapped_column(Integer)
