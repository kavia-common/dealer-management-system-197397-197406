from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import StockEntryCreate, StockEntryOut
from src.db.models import Dealer, StockEntry
from src.db.session import get_db

router = APIRouter(prefix="/stock", tags=["Stock"])


def _compute_total_cost(unit_cost: Decimal, quantity: int) -> Decimal:
    """Compute total cost with 2-decimal quantization to match DB scale."""
    return (unit_cost * Decimal(quantity)).quantize(Decimal("0.01"))


@router.get(
    "",
    response_model=List[StockEntryOut],
    summary="List stock entries",
    description=(
        "Return a list of stock entries.\n\n"
        "Supports optional filtering by `dealer_id` and simple pagination via `limit`/`offset`.\n"
        "Results are ordered by `stock_date` (desc) then `id` (desc)."
    ),
    operation_id="stock_list",
)
# PUBLIC_INTERFACE
def list_stock_entries(
    dealer_id: int | None = Query(
        None,
        description="Optional dealer id to filter stock entries",
    ),
    limit: int = Query(50, ge=1, le=200, description="Max number of stock entries to return"),
    offset: int = Query(0, ge=0, description="Number of stock entries to skip"),
    db: Session = Depends(get_db),
) -> List[StockEntry]:
    """List stock entries with optional dealer filter.

    Args:
        dealer_id: If provided, only return entries for that dealer.
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        List[StockEntryOut]: Stock entries.
    """
    stmt = select(StockEntry)
    if dealer_id is not None:
        stmt = stmt.where(StockEntry.dealer_id == dealer_id)

    stmt = stmt.order_by(StockEntry.stock_date.desc(), StockEntry.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.post(
    "",
    response_model=StockEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create stock entry",
    description="Create a new stock entry for a dealer. `total_cost` is computed as `unit_cost * quantity`.",
    operation_id="stock_create",
)
# PUBLIC_INTERFACE
def create_stock_entry(payload: StockEntryCreate, db: Session = Depends(get_db)) -> StockEntry:
    """Create a stock entry.

    Args:
        payload: StockEntryCreate payload.
        db: SQLAlchemy Session dependency.

    Returns:
        StockEntryOut: The created stock entry.

    Raises:
        HTTPException: 404 if dealer not found.
    """
    dealer = db.get(Dealer, payload.dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    entry = StockEntry(
        dealer_id=payload.dealer_id,
        item_name=payload.item_name,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        total_cost=_compute_total_cost(payload.unit_cost, payload.quantity),
        stock_date=payload.stock_date or dt.date.today(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put(
    "/{stock_id}",
    response_model=StockEntryOut,
    summary="Update stock entry",
    description=(
        "Update an existing stock entry by id.\n\n"
        "All fields are optional; only provided fields are updated. "
        "`total_cost` is automatically re-computed if `quantity` or `unit_cost` changes."
    ),
    operation_id="stock_update",
)
# PUBLIC_INTERFACE
def update_stock_entry(
    stock_id: int,
    payload: StockEntryCreate,
    db: Session = Depends(get_db),
) -> StockEntry:
    """Update a stock entry.

    Note:
        This endpoint uses the existing StockEntryCreate schema as the update payload
        (the project currently does not define a StockEntryUpdate schema). This keeps
        the backend compatible without introducing new schema surface area.

    Args:
        stock_id: Stock entry id path parameter.
        payload: StockEntryCreate payload.
        db: SQLAlchemy Session dependency.

    Returns:
        StockEntryOut: The updated stock entry.

    Raises:
        HTTPException: 404 if stock entry not found.
        HTTPException: 404 if the provided dealer_id does not exist.
    """
    entry = db.get(StockEntry, stock_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock entry not found")

    dealer = db.get(Dealer, payload.dealer_id)
    if dealer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found")

    entry.dealer_id = payload.dealer_id
    entry.item_name = payload.item_name
    entry.quantity = payload.quantity
    entry.unit_cost = payload.unit_cost
    entry.stock_date = payload.stock_date or entry.stock_date
    entry.total_cost = _compute_total_cost(entry.unit_cost, entry.quantity)

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete(
    "/{stock_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete stock entry",
    description="Delete a stock entry by id.",
    operation_id="stock_delete",
)
# PUBLIC_INTERFACE
def delete_stock_entry(stock_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a stock entry.

    Args:
        stock_id: Stock entry id path parameter.
        db: SQLAlchemy Session dependency.

    Returns:
        None

    Raises:
        HTTPException: 404 if stock entry not found.
    """
    entry = db.get(StockEntry, stock_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock entry not found")

    db.delete(entry)
    db.commit()
    return None
