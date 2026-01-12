from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Dealer, Payment, PayrollCredit, StockEntry


# PUBLIC_INTERFACE
def create_dealer(db: Session, *, name: str, phone: str | None, address: str | None) -> Dealer:
    """Create a dealer record."""
    dealer = Dealer(name=name, phone=phone, address=address)
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return dealer


# PUBLIC_INTERFACE
def list_dealers(db: Session) -> list[Dealer]:
    """Return all dealers."""
    return list(db.execute(select(Dealer).order_by(Dealer.name.asc())).scalars().all())


# PUBLIC_INTERFACE
def get_dealer(db: Session, dealer_id: int) -> Dealer | None:
    """Fetch a dealer by id."""
    return db.get(Dealer, dealer_id)


# PUBLIC_INTERFACE
def create_stock_entry(
    db: Session,
    *,
    dealer_id: int,
    item_name: str,
    quantity: int,
    unit_cost: Decimal,
    stock_date: dt.date | None,
) -> StockEntry:
    """Create a stock entry; total_cost computed."""
    total_cost = (unit_cost * Decimal(quantity)).quantize(Decimal("0.01"))
    entry = StockEntry(
        dealer_id=dealer_id,
        item_name=item_name,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        stock_date=stock_date or dt.date.today(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# PUBLIC_INTERFACE
def create_payroll_credit(
    db: Session,
    *,
    dealer_id: int,
    description: str | None,
    amount: Decimal,
    credit_date: dt.date | None,
) -> PayrollCredit:
    """Create a payroll/credit entry."""
    credit = PayrollCredit(
        dealer_id=dealer_id,
        description=description,
        amount=amount,
        credit_date=credit_date or dt.date.today(),
    )
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return credit


# PUBLIC_INTERFACE
def create_payment(
    db: Session,
    *,
    dealer_id: int,
    amount: Decimal,
    paid_at: dt.datetime | None,
    note: str | None,
) -> Payment:
    """Create a payment record."""
    payment = Payment(
        dealer_id=dealer_id,
        amount=amount,
        paid_at=paid_at or dt.datetime.utcnow(),
        note=note,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


# PUBLIC_INTERFACE
def compute_dealer_ledger_summary(db: Session, dealer_id: int) -> dict[str, Decimal] | None:
    """Compute ledger summary totals for a dealer.

    Returns:
        dict with keys: stock_total, payroll_credit_total, payments_total, balance_due
        or None if dealer doesn't exist.
    """
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        return None

    stock_total = db.execute(
        select(func.coalesce(func.sum(StockEntry.total_cost), 0)).where(StockEntry.dealer_id == dealer_id)
    ).scalar_one()
    payroll_total = db.execute(
        select(func.coalesce(func.sum(PayrollCredit.amount), 0)).where(PayrollCredit.dealer_id == dealer_id)
    ).scalar_one()
    payments_total = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.dealer_id == dealer_id)
    ).scalar_one()

    # Ensure Decimal output (psycopg2 usually already returns Decimal for Numeric)
    stock_total = Decimal(stock_total)
    payroll_total = Decimal(payroll_total)
    payments_total = Decimal(payments_total)

    balance_due = (stock_total + payroll_total - payments_total).quantize(Decimal("0.01"))

    return {
        "stock_total": stock_total.quantize(Decimal("0.01")),
        "payroll_credit_total": payroll_total.quantize(Decimal("0.01")),
        "payments_total": payments_total.quantize(Decimal("0.01")),
        "balance_due": balance_due,
    }
