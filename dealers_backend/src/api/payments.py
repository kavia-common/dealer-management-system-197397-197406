from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Dealer, Payment
from src.db.session import get_db

router = APIRouter(prefix="/payments", tags=["Payments"])


def _q2(value: Decimal) -> Decimal:
    """Quantize to 2 decimals to match DB Numeric(12,2)."""
    return Decimal(value).quantize(Decimal("0.01"))


class PaymentCreateIn(BaseModel):
    """Create/update payload compatible with the frontend PaymentsPage.

    This endpoint is intentionally "frontend-compatible" (camelCase) and maps into the
    existing Postgres `payments` table columns.

    DB columns:
      - payment_date (date)
      - notes (text)
      - method (text)
      - reference (text)
    """

    dealerId: int = Field(..., description="Dealer id")
    amount: Decimal = Field(..., gt=0, description="Payment amount (> 0)")
    paymentDate: Optional[dt.date] = Field(None, description="Payment date (YYYY-MM-DD). Defaults to today.")
    notes: Optional[str] = Field(None, description="Payment notes/remark")
    method: Optional[str] = Field(None, description="Payment method")
    reference: Optional[str] = Field(None, description="Optional reference (receipt/invoice #)")
    status: Optional[Literal["PAID", "UNPAID"]] = Field(
        None,
        description='Payment status. "UNPAID" is not persisted as a Payment record.',
    )


class PaymentOutCompat(BaseModel):
    """Response model that matches frontend normalization fields."""

    id: int = Field(..., description="Payment id")
    dealerId: int = Field(..., description="Dealer id")
    dealerName: str = Field(..., description="Dealer name")
    amount: Decimal = Field(..., description="Payment amount")
    method: str = Field("", description="Payment method")
    notes: str = Field("", description="Payment notes")
    reference: str = Field("", description="Reference")
    paymentDate: dt.date = Field(..., description="Payment date")
    status: Literal["PAID"] = Field("PAID", description='Always "PAID" for persisted payment records.')


def _to_out(payment: Payment, dealer_name: str) -> PaymentOutCompat:
    """Map ORM Payment model to frontend-compatible response."""
    return PaymentOutCompat(
        id=payment.id,
        dealerId=payment.dealer_id,
        dealerName=dealer_name,
        amount=payment.amount,
        method=payment.method or "",
        notes=payment.notes or "",
        reference=payment.reference or "",
        paymentDate=payment.payment_date,
        status="PAID",
    )


@router.get(
    "",
    response_model=List[PaymentOutCompat],
    summary="List payments",
    description=(
        "Return a list of payment records.\n\n"
        "Supports optional filtering by `dealerId` and `status`.\n"
        "Note: Only persisted payments exist, therefore `status=UNPAID` returns an empty list.\n\n"
        "Results are ordered by `payment_date` (desc) then `id` (desc)."
    ),
    operation_id="payments_list",
)
# PUBLIC_INTERFACE
def list_payments(
    dealerId: int | None = Query(None, description="Optional dealer id to filter payments"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description='Optional status filter ("PAID" or "UNPAID"). "UNPAID" returns empty list.',
    ),
    limit: int = Query(50, ge=1, le=200, description="Max number of payments to return"),
    offset: int = Query(0, ge=0, description="Number of payments to skip"),
    db: Session = Depends(get_db),
) -> List[PaymentOutCompat]:
    """List payment records with optional dealer and status filters."""
    if status_filter is not None and str(status_filter).upper() == "UNPAID":
        return []

    stmt = select(Payment, Dealer.name).join(Dealer, Dealer.id == Payment.dealer_id)
    if dealerId is not None:
        stmt = stmt.where(Payment.dealer_id == dealerId)

    stmt = stmt.order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).all()
    return [_to_out(payment=row[0], dealer_name=row[1]) for row in rows]


@router.post(
    "",
    response_model=PaymentOutCompat,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment",
    description=(
        "Create a new payment record for a dealer.\n\n"
        'If payload `status` is "UNPAID", the request is rejected because unpaid entries are not stored as payments.'
    ),
    operation_id="payments_create",
)
# PUBLIC_INTERFACE
def create_payment(payload: PaymentCreateIn, db: Session = Depends(get_db)) -> PaymentOutCompat:
    """Create a payment record."""
    if payload.status is not None and payload.status.upper() == "UNPAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot create an "UNPAID" payment record. Use PAID status to persist a payment.',
        )

    dealer = db.get(Dealer, payload.dealerId)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    payment = Payment(
        dealer_id=payload.dealerId,
        amount=_q2(payload.amount),
        payment_date=payload.paymentDate or dt.date.today(),
        method=(payload.method or None),
        reference=(payload.reference or None),
        notes=(payload.notes or None),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return _to_out(payment, dealer.name)


@router.put(
    "/{payment_id}",
    response_model=PaymentOutCompat,
    summary="Update payment",
    description=(
        "Update an existing payment record by id.\n\n"
        'If payload `status` is "UNPAID", the payment record is deleted (interpreted as marking it unpaid).'
    ),
    operation_id="payments_update",
)
# PUBLIC_INTERFACE
def update_payment(payment_id: int, payload: PaymentCreateIn, db: Session = Depends(get_db)) -> PaymentOutCompat:
    """Update a payment record."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payload.status is not None and payload.status.upper() == "UNPAID":
        db.delete(payment)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment marked UNPAID (record removed). Refresh the list.",
        )

    dealer = db.get(Dealer, payload.dealerId)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    payment.dealer_id = payload.dealerId
    payment.amount = _q2(payload.amount)
    payment.payment_date = payload.paymentDate or payment.payment_date
    payment.method = (payload.method or None)
    payment.reference = (payload.reference or None)
    payment.notes = (payload.notes or None)

    db.add(payment)
    db.commit()
    db.refresh(payment)
    return _to_out(payment, dealer.name)


@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete payment",
    description="Delete a payment record by id.",
    operation_id="payments_delete",
)
# PUBLIC_INTERFACE
def delete_payment(payment_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a payment record."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    db.delete(payment)
    db.commit()
    return None
