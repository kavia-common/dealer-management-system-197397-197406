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


class FinanceTotals(BaseModel):
    """Overall finance totals for dashboard/reporting."""
    totalStockValue: Decimal = Field(..., description="Sum of all stock_entries.total_cost across all dealers")
    totalCredits: Decimal = Field(..., description="Sum of all payroll_credits.amount across all dealers")
    totalPayments: Decimal = Field(..., description="Sum of all payments.amount across all dealers")
    outstandingBalance: Decimal = Field(
        ...,
        description="(totalStockValue + totalCredits) - totalPayments",
    )


class FinancePerDealerSummary(BaseModel):
    """Per-dealer finance summary row for list/table views."""
    id: int = Field(..., description="Dealer id")
    name: str = Field(..., description="Dealer name")

    stockTotal: Decimal = Field(..., description="Dealer stock total")
    creditTotal: Decimal = Field(..., description="Dealer payroll/credit total")
    paymentsTotal: Decimal = Field(..., description="Dealer payments total")
    outstandingBalance: Decimal = Field(
        ...,
        description="(stockTotal + creditTotal) - paymentsTotal",
    )

    paidCount: int = Field(..., description="Count of payment records for dealer")
    unpaidCount: int = Field(
        ...,
        description="Count of unpaid stock entries for dealer (derived: stock entries with no matching payment record)",
    )


class FinanceActivityItem(BaseModel):
    """A single item in the finance activity/ledger feed."""
    type: str = Field(
        ...,
        description='Activity type such as "STOCK", "CREDIT", or "PAYMENT".',
    )
    id: int = Field(..., description="Underlying row id of the source record")
    dealerId: int = Field(..., description="Dealer id")
    dealerName: str = Field(..., description="Dealer name")
    amount: Decimal = Field(..., description="Amount for the activity (stock total_cost, credit amount, payment amount)")
    occurredAt: dt.datetime = Field(..., description="Timestamp for ordering the activity feed")
    description: str = Field("", description="Optional activity description (item_name, credit description, payment note)")


class FinanceActivityPage(BaseModel):
    """Paginated activity feed response."""
    items: list[FinanceActivityItem] = Field(..., description="Activity items ordered by occurredAt desc")
    limit: int = Field(..., description="Page size used")
    offset: int = Field(..., description="Offset used")
