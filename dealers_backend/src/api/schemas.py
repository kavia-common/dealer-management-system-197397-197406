from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class _ORMModel(BaseModel):
    """Base class enabling ORM mode for Pydantic v2."""
    model_config = ConfigDict(from_attributes=True)


# -----------------------
# Dealer schemas
# -----------------------
class DealerCreate(BaseModel):
    name: str = Field(..., description="Dealer name")
    phone: Optional[str] = Field(None, description="Dealer phone number")
    address: Optional[str] = Field(None, description="Dealer address")


class DealerUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Dealer name")
    phone: Optional[str] = Field(None, description="Dealer phone number")
    address: Optional[str] = Field(None, description="Dealer address")


class DealerOut(_ORMModel):
    id: int
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime


# -----------------------
# Stock entry schemas
# -----------------------
class StockEntryCreate(BaseModel):
    dealer_id: int = Field(..., description="Dealer id")
    item_name: str = Field(..., description="Item name/description")
    quantity: int = Field(..., ge=1, description="Quantity")
    unit_cost: Decimal = Field(..., ge=0, description="Unit cost")
    stock_date: Optional[dt.date] = Field(None, description="Stock entry date (defaults to today)")


class StockEntryOut(_ORMModel):
    id: int
    dealer_id: int
    item_name: str
    quantity: int
    unit_cost: Decimal
    total_cost: Decimal
    stock_date: dt.date
    created_at: dt.datetime


# -----------------------
# Payroll/Credit schemas
# -----------------------
class PayrollCreditCreate(BaseModel):
    dealer_id: int = Field(..., description="Dealer id")
    description: Optional[str] = Field(None, description="Reason/notes for the credit")
    amount: Decimal = Field(..., ge=0, description="Credit amount")
    credit_date: Optional[dt.date] = Field(None, description="Credit date (defaults to today)")


class PayrollCreditOut(_ORMModel):
    id: int
    dealer_id: int
    description: Optional[str] = None
    amount: Decimal
    credit_date: dt.date
    created_at: dt.datetime


# -----------------------
# Payment schemas
# -----------------------
class PaymentCreate(BaseModel):
    dealer_id: int = Field(..., description="Dealer id")
    amount: Decimal = Field(..., ge=0, description="Payment amount")
    paid_at: Optional[dt.datetime] = Field(None, description="Payment timestamp (defaults to now)")
    note: Optional[str] = Field(None, description="Payment note/remark")


class PaymentOut(_ORMModel):
    id: int
    dealer_id: int
    amount: Decimal
    paid_at: dt.datetime
    note: Optional[str] = None
    created_at: dt.datetime


# -----------------------
# Reporting / Ledger schemas
# -----------------------
class DealerLedgerSummary(BaseModel):
    """Computed summary for a dealer ledger used by reporting endpoints."""
    dealer_id: int = Field(..., description="Dealer id")
    dealer_name: str = Field(..., description="Dealer name")
    stock_total: Decimal = Field(..., description="Sum of stock entry total_cost for dealer")
    payroll_credit_total: Decimal = Field(..., description="Sum of payroll/credit amounts for dealer")
    payments_total: Decimal = Field(..., description="Sum of payments for dealer")
    balance_due: Decimal = Field(..., description="(stock_total + payroll_credit_total) - payments_total")
