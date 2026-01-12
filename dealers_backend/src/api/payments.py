from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Dealer, Payment
from src.db.session import get_db

router = APIRouter(prefix="/payments", tags=["Payments"])


class PaymentStatusOut(BaseModel):
    """Payment status enum-like output model.

    The frontend expects "PAID" | "UNPAID" (or null).
    """

    model_config = ConfigDict(from_attributes=True)

    status: Literal["PAID", "UNPAID"] = Field(..., description='Payment status: "PAID" or "UNPAID".')


class PaymentCreateIn(BaseModel):
    """Create/update payload compatible with the frontend PaymentsPage.

    Notes:
      - The backend stores only `paid_at`, `amount`, `note`. There is no dedicated "unpaid payment" record.
      - We therefore interpret `status`:
          * "PAID"  -> create/update a real Payment record
          * "UNPAID" -> reject (client should not create unpaid records in DB)
      - `paymentDate` is accepted as a date string and mapped to paid_at (00:00:00 UTC-ish naive datetime).
    """

    dealerId: int = Field(..., description="Dealer id")
    amount: Decimal = Field(..., ge=0, description="Payment amount")
    paymentDate: Optional[dt.date] = Field(None, description="Payment date (YYYY-MM-DD). Defaults to today.")
    notes: Optional[str] = Field(None, description="Payment notes/remark")
    method: Optional[str] = Field(None, description="Payment method (stored into notes for compatibility)")
    status: Optional[Literal["PAID", "UNPAID"]] = Field(
        None,
        description='Payment status. Only "PAID" is persisted as a Payment record.',
    )


class PaymentOutCompat(BaseModel):
    """Response model that matches frontend normalization fields.

    The UI normalizer supports many aliases, but we return the preferred fields:
      - dealerId, dealerName
      - paymentDate
      - notes, method
      - status
    """

    id: int = Field(..., description="Payment id")
    dealerId: int = Field(..., description="Dealer id")
    dealerName: str = Field(..., description="Dealer name")
    amount: Decimal = Field(..., description="Payment amount")
    method: str = Field("", description="Payment method")
    notes: str = Field("", description="Payment notes")
    paymentDate: dt.datetime = Field(..., description="Payment timestamp")
    status: Literal["PAID"] = Field("PAID", description='Always "PAID" for persisted payment records.')


def _q2(value: Decimal) -> Decimal:
    """Quantize to 2 decimals to match DB Numeric(12,2)."""
    return Decimal(value).quantize(Decimal("0.01"))


def _compose_note(notes: str | None, method: str | None) -> str | None:
    """Combine method+notes into a single persisted note field.

    Since DB model only has `note`, we store method as a prefix for round-tripping with UI.
    """
    notes = (notes or "").strip()
    method = (method or "").strip()
    if not notes and not method:
        return None
    if method and notes:
        return f"Method: {method}\n{notes}"
    if method and not notes:
        return f"Method: {method}"
    return notes


def _split_note(note: str | None) -> tuple[str, str]:
    """Attempt to parse method prefix from persisted note.

    Returns:
        (method, notes)
    """
    if not note:
        return ("", "")
    lines = note.splitlines()
    if lines and lines[0].lower().startswith("method:"):
        method = lines[0].split(":", 1)[1].strip()
        remaining = "\n".join(lines[1:]).strip()
        return (method, remaining)
    return ("", note)


def _to_paid_at(payment_date: dt.date | None) -> dt.datetime:
    """Convert a date to a datetime for `paid_at`."""
    d = payment_date or dt.date.today()
    return dt.datetime(d.year, d.month, d.day)


def _to_out(payment: Payment, dealer_name: str) -> PaymentOutCompat:
    """Map ORM Payment model to frontend-compatible response."""
    method, notes = _split_note(payment.note)
    return PaymentOutCompat(
        id=payment.id,
        dealerId=payment.dealer_id,
        dealerName=dealer_name,
        amount=payment.amount,
        method=method,
        notes=notes,
        paymentDate=payment.paid_at,
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
        "Results are ordered by `paid_at` (desc) then `id` (desc)."
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
    """List payment records with optional dealer and status filters.

    Args:
        dealerId: Optional dealer id filter.
        status_filter: Optional status filter. Only "PAID" is supported for persisted payments.
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        List[PaymentOutCompat]: List of payments.
    """
    if status_filter is not None and str(status_filter).upper() == "UNPAID":
        return []

    stmt = select(Payment, Dealer.name).join(Dealer, Dealer.id == Payment.dealer_id)
    if dealerId is not None:
        stmt = stmt.where(Payment.dealer_id == dealerId)

    stmt = stmt.order_by(Payment.paid_at.desc(), Payment.id.desc()).limit(limit).offset(offset)

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
    """Create a payment record.

    Args:
        payload: PaymentCreateIn payload (frontend-compatible).
        db: SQLAlchemy Session dependency.

    Returns:
        PaymentOutCompat: Created payment record.

    Raises:
        HTTPException: 404 if dealer not found.
        HTTPException: 400 if status is UNPAID.
    """
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
        paid_at=_to_paid_at(payload.paymentDate),
        note=_compose_note(payload.notes, payload.method),
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
    """Update a payment record.

    Status handling:
      - PAID (or null): update the Payment record
      - UNPAID: delete the Payment record (so it no longer counts as a payment)

    Args:
        payment_id: Payment id path parameter.
        payload: PaymentCreateIn payload.
        db: SQLAlchemy Session dependency.

    Returns:
        PaymentOutCompat: Updated payment record.

    Raises:
        HTTPException: 404 if payment not found.
        HTTPException: 404 if dealer not found.
    """
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
    payment.paid_at = _to_paid_at(payload.paymentDate) if payload.paymentDate else payment.paid_at
    payment.note = _compose_note(payload.notes, payload.method)

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
    """Delete a payment record.

    Args:
        payment_id: Payment id path parameter.
        db: SQLAlchemy Session dependency.

    Returns:
        None

    Raises:
        HTTPException: 404 if payment not found.
    """
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    db.delete(payment)
    db.commit()
    return None
