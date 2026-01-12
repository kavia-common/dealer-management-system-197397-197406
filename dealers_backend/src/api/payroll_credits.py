from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import DealerLedgerSummary, PayrollCreditCreate, PayrollCreditOut
from src.db.models import Dealer, PayrollCredit
from src.db.repositories import compute_dealer_ledger_summary
from src.db.session import get_db

router = APIRouter(prefix="/payroll_credits", tags=["Payroll/Credits"])


def _q2(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places to match DB Numeric(12,2) scale."""
    return Decimal(value).quantize(Decimal("0.01"))


@router.get(
    "",
    response_model=List[PayrollCreditOut],
    summary="List payroll credits",
    description=(
        "Return a list of payroll/credit entries.\n\n"
        "Supports optional filtering by `dealer_id` and simple pagination via `limit`/`offset`.\n"
        "Results are ordered by `credit_date` (desc) then `id` (desc)."
    ),
    operation_id="payroll_credits_list",
)
# PUBLIC_INTERFACE
def list_payroll_credits(
    dealer_id: int | None = Query(
        None,
        description="Optional dealer id to filter payroll/credits",
    ),
    limit: int = Query(50, ge=1, le=200, description="Max number of payroll credits to return"),
    offset: int = Query(0, ge=0, description="Number of payroll credits to skip"),
    db: Session = Depends(get_db),
) -> List[PayrollCredit]:
    """List payroll/credit entries with optional dealer filter.

    Args:
        dealer_id: If provided, only return entries for that dealer.
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        List[PayrollCreditOut]: Payroll/credit entries.
    """
    stmt = select(PayrollCredit)
    if dealer_id is not None:
        stmt = stmt.where(PayrollCredit.dealer_id == dealer_id)

    stmt = stmt.order_by(PayrollCredit.credit_date.desc(), PayrollCredit.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.post(
    "",
    response_model=PayrollCreditOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create payroll credit",
    description="Create a new payroll/credit entry for a dealer.",
    operation_id="payroll_credits_create",
)
# PUBLIC_INTERFACE
def create_payroll_credit(payload: PayrollCreditCreate, db: Session = Depends(get_db)) -> PayrollCredit:
    """Create a payroll/credit entry.

    Args:
        payload: PayrollCreditCreate payload.
        db: SQLAlchemy Session dependency.

    Returns:
        PayrollCreditOut: The created payroll/credit entry.

    Raises:
        HTTPException: 404 if dealer not found.
    """
    dealer = db.get(Dealer, payload.dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    credit = PayrollCredit(
        dealer_id=payload.dealer_id,
        description=payload.description,
        amount=_q2(payload.amount),
        credit_date=payload.credit_date or dt.date.today(),
    )
    db.add(credit)
    db.commit()
    db.refresh(credit)
    return credit


@router.put(
    "/{credit_id}",
    response_model=PayrollCreditOut,
    summary="Update payroll credit",
    description=(
        "Update an existing payroll/credit entry by id.\n\n"
        "Note: This endpoint uses the existing PayrollCreditCreate schema as the update payload "
        "(the project currently does not define a PayrollCreditUpdate schema)."
    ),
    operation_id="payroll_credits_update",
)
# PUBLIC_INTERFACE
def update_payroll_credit(
    credit_id: int,
    payload: PayrollCreditCreate,
    db: Session = Depends(get_db),
) -> PayrollCredit:
    """Update a payroll/credit entry.

    Args:
        credit_id: Payroll/credit entry id path parameter.
        payload: PayrollCreditCreate payload.
        db: SQLAlchemy Session dependency.

    Returns:
        PayrollCreditOut: The updated payroll/credit entry.

    Raises:
        HTTPException: 404 if payroll credit not found.
        HTTPException: 404 if the provided dealer_id does not exist.
    """
    credit = db.get(PayrollCredit, credit_id)
    if credit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll credit not found")

    dealer = db.get(Dealer, payload.dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    credit.dealer_id = payload.dealer_id
    credit.description = payload.description
    credit.amount = _q2(payload.amount)
    credit.credit_date = payload.credit_date or credit.credit_date

    db.add(credit)
    db.commit()
    db.refresh(credit)
    return credit


@router.delete(
    "/{credit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete payroll credit",
    description="Delete a payroll/credit entry by id.",
    operation_id="payroll_credits_delete",
)
# PUBLIC_INTERFACE
def delete_payroll_credit(credit_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a payroll/credit entry.

    Args:
        credit_id: Payroll/credit entry id path parameter.
        db: SQLAlchemy Session dependency.

    Returns:
        None

    Raises:
        HTTPException: 404 if payroll credit not found.
    """
    credit = db.get(PayrollCredit, credit_id)
    if credit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll credit not found")

    db.delete(credit)
    db.commit()
    return None


@router.get(
    "/dealer/{dealer_id}/summary",
    response_model=DealerLedgerSummary,
    summary="Get dealer balance summary",
    description=(
        "Compute and return a server-side ledger summary for a dealer.\n\n"
        "Balance formula:\n"
        "  balance_due = (stock_total + payroll_credit_total) - payments_total\n\n"
        "This is designed for the Payroll/Credits UI to show up-to-date balances without client-side aggregation."
    ),
    operation_id="dealer_balance_summary",
)
# PUBLIC_INTERFACE
def get_dealer_balance_summary(dealer_id: int, db: Session = Depends(get_db)) -> DealerLedgerSummary:
    """Compute and return ledger summary totals for a dealer.

    Args:
        dealer_id: Dealer id path parameter.
        db: SQLAlchemy Session dependency.

    Returns:
        DealerLedgerSummary: Totals and computed balance due.

    Raises:
        HTTPException: 404 if dealer not found.
    """
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    summary = compute_dealer_ledger_summary(db, dealer_id)
    if summary is None:
        # Defensive: repository already checks dealer existence, but keep consistent API behavior.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    return DealerLedgerSummary(
        dealer_id=dealer.id,
        dealer_name=dealer.name,
        stock_total=summary["stock_total"],
        payroll_credit_total=summary["payroll_credit_total"],
        payments_total=summary["payments_total"],
        balance_due=summary["balance_due"],
    )
