from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, literal, select
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


def _q2(value: Decimal) -> Decimal:
    """Quantize to 2 decimals to match Numeric(12,2) DB scale."""
    return Decimal(value).quantize(Decimal("0.01"))


# PUBLIC_INTERFACE
def compute_finance_totals(db: Session) -> dict[str, Decimal]:
    """Compute overall finance totals.

    Totals:
      - totalStockValue: sum(stock_entries.total_cost)
      - totalCredits: sum(payroll_credits.amount)
      - totalPayments: sum(payments.amount)
      - outstandingBalance: (totalStockValue + totalCredits) - totalPayments

    Args:
        db: SQLAlchemy session.

    Returns:
        dict[str, Decimal]: Totals as Decimals (2-decimal quantized).
    """
    stock_total = Decimal(
        db.execute(select(func.coalesce(func.sum(StockEntry.total_cost), 0))).scalar_one()
    )
    credit_total = Decimal(
        db.execute(select(func.coalesce(func.sum(PayrollCredit.amount), 0))).scalar_one()
    )
    payments_total = Decimal(
        db.execute(select(func.coalesce(func.sum(Payment.amount), 0))).scalar_one()
    )

    outstanding = _q2(stock_total + credit_total - payments_total)

    return {
        "totalStockValue": _q2(stock_total),
        "totalCredits": _q2(credit_total),
        "totalPayments": _q2(payments_total),
        "outstandingBalance": outstanding,
    }


# PUBLIC_INTERFACE
def list_finance_per_dealer_summaries(db: Session, *, limit: int, offset: int) -> list[dict]:
    """Return per-dealer finance summaries.

    This is designed for dashboard tables and supports pagination.

    unpaidCount is derived from:
        max(stock_entries_count - payments_count, 0)

    Args:
        db: SQLAlchemy session.
        limit: Page size.
        offset: Offset.

    Returns:
        list[dict]: List of dict rows with keys matching FinancePerDealerSummary.
    """
    # Aggregate stock totals and count
    stock_agg = (
        select(
            StockEntry.dealer_id.label("dealer_id"),
            func.coalesce(func.sum(StockEntry.total_cost), 0).label("stock_total"),
            func.count(StockEntry.id).label("stock_count"),
        )
        .group_by(StockEntry.dealer_id)
        .subquery()
    )

    # Aggregate credit totals
    credit_agg = (
        select(
            PayrollCredit.dealer_id.label("dealer_id"),
            func.coalesce(func.sum(PayrollCredit.amount), 0).label("credit_total"),
        )
        .group_by(PayrollCredit.dealer_id)
        .subquery()
    )

    # Aggregate payment totals and count
    payment_agg = (
        select(
            Payment.dealer_id.label("dealer_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("payments_total"),
            func.count(Payment.id).label("payments_count"),
        )
        .group_by(Payment.dealer_id)
        .subquery()
    )

    stmt = (
        select(
            Dealer.id,
            Dealer.name,
            func.coalesce(stock_agg.c.stock_total, 0).label("stock_total"),
            func.coalesce(credit_agg.c.credit_total, 0).label("credit_total"),
            func.coalesce(payment_agg.c.payments_total, 0).label("payments_total"),
            func.coalesce(payment_agg.c.payments_count, 0).label("paid_count"),
            func.coalesce(stock_agg.c.stock_count, 0).label("stock_count"),
        )
        .select_from(Dealer)
        .outerjoin(stock_agg, stock_agg.c.dealer_id == Dealer.id)
        .outerjoin(credit_agg, credit_agg.c.dealer_id == Dealer.id)
        .outerjoin(payment_agg, payment_agg.c.dealer_id == Dealer.id)
        .order_by(Dealer.name.asc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).all()
    results: list[dict] = []
    for r in rows:
        stock_total = _q2(Decimal(r.stock_total))
        credit_total = _q2(Decimal(r.credit_total))
        payments_total = _q2(Decimal(r.payments_total))

        paid_count = int(r.paid_count or 0)
        stock_count = int(r.stock_count or 0)
        unpaid_count = max(stock_count - paid_count, 0)

        outstanding = _q2(stock_total + credit_total - payments_total)

        results.append(
            {
                "id": int(r.id),
                "name": str(r.name),
                "stockTotal": stock_total,
                "creditTotal": credit_total,
                "paymentsTotal": payments_total,
                "outstandingBalance": outstanding,
                "paidCount": paid_count,
                "unpaidCount": unpaid_count,
            }
        )

    return results


# PUBLIC_INTERFACE
def list_finance_activity(db: Session, *, limit: int, offset: int) -> list[dict]:
    """Return a unified recent activity feed across stock entries, credits, and payments.

    This feed is intended for a simple ledger/recent activity list.

    Implementation notes:
      - We union three selects into one stream and order by occurredAt desc.
      - For stock entries and credits, occurredAt uses created_at.
      - For payments, occurredAt uses paid_at for more user-meaningful chronology.

    Args:
        db: SQLAlchemy session.
        limit: Page size.
        offset: Offset.

    Returns:
        list[dict]: Activity item dicts matching FinanceActivityItem fields.
    """
    stock_stmt = (
        select(
            literal("STOCK").label("type"),
            StockEntry.id.label("id"),
            Dealer.id.label("dealerId"),
            Dealer.name.label("dealerName"),
            StockEntry.total_cost.label("amount"),
            StockEntry.created_at.label("occurredAt"),
            StockEntry.item_name.label("description"),
        )
        .select_from(StockEntry)
        .join(Dealer, Dealer.id == StockEntry.dealer_id)
    )

    credit_stmt = (
        select(
            literal("CREDIT").label("type"),
            PayrollCredit.id.label("id"),
            Dealer.id.label("dealerId"),
            Dealer.name.label("dealerName"),
            PayrollCredit.amount.label("amount"),
            PayrollCredit.created_at.label("occurredAt"),
            func.coalesce(PayrollCredit.description, "").label("description"),
        )
        .select_from(PayrollCredit)
        .join(Dealer, Dealer.id == PayrollCredit.dealer_id)
    )

    payment_stmt = (
        select(
            literal("PAYMENT").label("type"),
            Payment.id.label("id"),
            Dealer.id.label("dealerId"),
            Dealer.name.label("dealerName"),
            Payment.amount.label("amount"),
            Payment.paid_at.label("occurredAt"),
            func.coalesce(Payment.note, "").label("description"),
        )
        .select_from(Payment)
        .join(Dealer, Dealer.id == Payment.dealer_id)
    )

    unioned = stock_stmt.union_all(credit_stmt, payment_stmt).subquery()

    ordered = (
        select(unioned)
        .order_by(unioned.c.occurredAt.desc(), unioned.c.type.asc(), unioned.c.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(ordered).mappings().all()
    items: list[dict] = []
    for row in rows:
        items.append(
            {
                "type": str(row["type"]),
                "id": int(row["id"]),
                "dealerId": int(row["dealerId"]),
                "dealerName": str(row["dealerName"]),
                "amount": _q2(Decimal(row["amount"])),
                "occurredAt": row["occurredAt"],
                "description": str(row["description"] or ""),
            }
        )
    return items
