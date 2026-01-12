from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, AliasChoices


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
    """Create payload for a stock entry.

    Note:
        The DB schema uses `entry_date`, but the API historically used `stock_date`.

        The React UI (and some earlier iterations of the API docs) may send camelCase
        keys like `dealerId`, `itemName`, `unitCost`, and `stockDate`/`entryDate`.

        To avoid UI↔API regressions, this schema explicitly accepts BOTH snake_case
        and camelCase variants via validation aliases, while keeping the canonical
        internal field names snake_case.
    """

    model_config = ConfigDict(populate_by_name=True)

    dealer_id: int = Field(
        ...,
        validation_alias=AliasChoices("dealer_id", "dealerId"),
        description="Dealer id",
    )
    item_name: str = Field(
        ...,
        validation_alias=AliasChoices("item_name", "itemName"),
        description="Item name/description",
    )
    quantity: Decimal = Field(..., ge=0, description="Quantity (numeric in DB)")
    unit_cost: Decimal = Field(
        ...,
        validation_alias=AliasChoices("unit_cost", "unitCost"),
        ge=0,
        description="Unit cost",
    )
    stock_date: Optional[dt.date] = Field(
        None,
        validation_alias=AliasChoices("stock_date", "stockDate", "entryDate", "entry_date"),
        description="Stock entry date (defaults to today)",
    )
    notes: Optional[str] = Field(None, description="Optional notes")


class StockEntryOut(_ORMModel):
    id: int
    dealer_id: int
    item_name: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal = Field(..., description="Derived as quantity * unit_cost (not stored)")
    stock_date: dt.date = Field(..., description="Alias of DB entry_date")
    notes: Optional[str] = None
    created_at: dt.datetime


# -----------------------
# Payroll/Credit schemas
# -----------------------
class PayrollCreditCreate(BaseModel):
    """Create payload for a payroll/credit entry.

    DB uses:
      - txn_type: 'PAYROLL' | 'CREDIT'
      - txn_date

    API keeps using `credit_date` naming for compatibility, but maps to txn_date.
    """
    dealer_id: int = Field(..., description="Dealer id")
    txn_type: str = Field(..., description="Transaction type: PAYROLL or CREDIT")
    description: Optional[str] = Field(None, description="Reason/notes for the entry")
    amount: Decimal = Field(..., ge=0, description="Amount (positive)")
    credit_date: Optional[dt.date] = Field(None, description="Transaction date (defaults to today)")


class PayrollCreditOut(_ORMModel):
    id: int
    dealer_id: int
    txn_type: str
    description: Optional[str] = None
    amount: Decimal
    credit_date: dt.date = Field(..., description="Alias of DB txn_date")
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
