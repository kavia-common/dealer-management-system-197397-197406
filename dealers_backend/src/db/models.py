from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base for all ORM models."""


class Dealer(Base):
    """Dealer entity."""
    __tablename__ = "dealers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stock_entries: Mapped[List["StockEntry"]] = relationship(
        back_populates="dealer", cascade="all, delete-orphan"
    )
    payroll_credits: Mapped[List["PayrollCredit"]] = relationship(
        back_populates="dealer", cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="dealer", cascade="all, delete-orphan"
    )


class StockEntry(Base):
    """Stock purchase/entry from a dealer."""
    __tablename__ = "stock_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="CASCADE"), index=True)

    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    stock_date: Mapped[dt.date] = mapped_column(Date, nullable=False, default=dt.date.today)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="stock_entries")


class PayrollCredit(Base):
    """Represents a payroll/credit entry associated with a dealer (amount owed to dealer)."""
    __tablename__ = "payroll_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="CASCADE"), index=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    credit_date: Mapped[dt.date] = mapped_column(Date, nullable=False, default=dt.date.today)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="payroll_credits")


class Payment(Base):
    """Payment made to a dealer (settlement)."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="CASCADE"), index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=dt.datetime.utcnow
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="payments")
