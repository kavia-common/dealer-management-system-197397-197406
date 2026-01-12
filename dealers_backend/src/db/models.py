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
    """Stock purchase/entry from a dealer.

    IMPORTANT: This model matches the existing Postgres schema in dealers_database.

    Table: stock_entries
      - entry_date (date) is the business date
      - quantity is numeric(12,2) in DB (legacy), but semantically represents a count
      - there is no persisted total_cost column; total is derived as quantity * unit_cost
    """
    __tablename__ = "stock_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="RESTRICT"), index=True)

    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False, default=dt.date.today)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="stock_entries")


class PayrollCredit(Base):
    """Payroll/Credit entry associated with a dealer.

    IMPORTANT: This model matches the existing Postgres schema in dealers_database.

    Table: payroll_credits
      - txn_type is 'PAYROLL' | 'CREDIT'
      - txn_date is the business date
    """
    __tablename__ = "payroll_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="RESTRICT"), index=True)

    txn_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    txn_date: Mapped[dt.date] = mapped_column(Date, nullable=False, default=dt.date.today)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="payroll_credits")


class Payment(Base):
    """Payment received from a dealer.

    IMPORTANT: This model matches the existing Postgres schema in dealers_database.

    Table: payments
      - payment_date is the business date (date)
      - notes/method/reference are stored as separate columns
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dealer_id: Mapped[int] = mapped_column(ForeignKey("dealers.id", ondelete="RESTRICT"), index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[dt.date] = mapped_column(Date, nullable=False, default=dt.date.today)

    method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="payments")
