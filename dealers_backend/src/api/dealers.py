from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.schemas import DealerCreate, DealerOut, DealerUpdate
from src.db.models import Dealer
from src.db.session import get_db

router = APIRouter(prefix="/dealers", tags=["Dealers"])


@router.get(
    "",
    response_model=List[DealerOut],
    summary="List dealers",
    description=(
        "Return a paginated list of dealers ordered by name.\n\n"
        "Pagination uses `limit` and `offset`."
    ),
    operation_id="dealers_list",
)
# PUBLIC_INTERFACE
def list_dealers(
    limit: int = Query(50, ge=1, le=200, description="Max number of dealers to return"),
    offset: int = Query(0, ge=0, description="Number of dealers to skip"),
    db: Session = Depends(get_db),
) -> List[Dealer]:
    """List dealers with simple pagination.

    Args:
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        List[DealerOut]: Dealers in ascending name order.
    """
    stmt = select(Dealer).order_by(Dealer.name.asc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.post(
    "",
    response_model=DealerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create dealer",
    description="Create a new dealer record.",
    operation_id="dealers_create",
)
# PUBLIC_INTERFACE
def create_dealer(payload: DealerCreate, db: Session = Depends(get_db)) -> Dealer:
    """Create a dealer.

    Args:
        payload: DealerCreate payload.
        db: SQLAlchemy Session dependency.

    Returns:
        DealerOut: The created dealer.

    Raises:
        HTTPException: 409 if dealer name already exists (DB unique constraint).
    """
    dealer = Dealer(name=payload.name, phone=payload.phone, address=payload.address)
    db.add(dealer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dealer with this name already exists",
        )
    db.refresh(dealer)
    return dealer


@router.put(
    "/{dealer_id}",
    response_model=DealerOut,
    summary="Update dealer",
    description="Update an existing dealer by id. Only provided fields are changed.",
    operation_id="dealers_update",
)
# PUBLIC_INTERFACE
def update_dealer(dealer_id: int, payload: DealerUpdate, db: Session = Depends(get_db)) -> Dealer:
    """Update a dealer.

    Args:
        dealer_id: Dealer id path parameter.
        payload: DealerUpdate payload (all fields optional).
        db: SQLAlchemy Session dependency.

    Returns:
        DealerOut: The updated dealer.

    Raises:
        HTTPException: 404 if dealer not found.
        HTTPException: 400 if no fields were provided to update.
    """
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    for key, value in updates.items():
        setattr(dealer, key, value)

    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return dealer


@router.delete(
    "/{dealer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete dealer",
    description="Delete a dealer by id. Cascades to related stock entries, credits, and payments.",
    operation_id="dealers_delete",
)
# PUBLIC_INTERFACE
def delete_dealer(dealer_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a dealer.

    Args:
        dealer_id: Dealer id path parameter.
        db: SQLAlchemy Session dependency.

    Returns:
        None

    Raises:
        HTTPException: 404 if dealer not found.
    """
    dealer = db.get(Dealer, dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    db.delete(dealer)
    db.commit()
    return None
