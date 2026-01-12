from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    FinanceActivityItem,
    FinanceActivityPage,
    FinancePerDealerSummary,
    FinanceTotals,
)
from src.db.repositories import compute_finance_totals, list_finance_activity, list_finance_per_dealer_summaries
from src.db.session import get_db

router = APIRouter(prefix="/finance", tags=["Finance"])


def _iso_now() -> str:
    """Return an ISO timestamp string for response metadata."""
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@router.get(
    "/totals",
    response_model=FinanceTotals,
    summary="Get overall finance totals",
    description=(
        "Compute overall totals for finance reporting.\n\n"
        "Totals are computed server-side using database aggregates."
    ),
    operation_id="finance_totals",
)
# PUBLIC_INTERFACE
def get_finance_totals(db: Session = Depends(get_db)) -> FinanceTotals:
    """Get overall finance totals.

    Args:
        db: SQLAlchemy Session dependency.

    Returns:
        FinanceTotals: Aggregated totals across all dealers.
    """
    totals = compute_finance_totals(db)
    return FinanceTotals(**totals)


@router.get(
    "/dealers",
    response_model=List[FinancePerDealerSummary],
    summary="List per-dealer finance summaries",
    description=(
        "Return a paginated list of per-dealer summaries.\n\n"
        "This endpoint is intended for finance dashboard tables."
    ),
    operation_id="finance_dealers_summary_list",
)
# PUBLIC_INTERFACE
def list_finance_dealers(
    limit: int = Query(50, ge=1, le=200, description="Max number of dealers to return"),
    offset: int = Query(0, ge=0, description="Number of dealers to skip"),
    db: Session = Depends(get_db),
) -> List[FinancePerDealerSummary]:
    """List per-dealer finance summary rows.

    Args:
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        List[FinancePerDealerSummary]: Per-dealer summaries.
    """
    rows = list_finance_per_dealer_summaries(db, limit=limit, offset=offset)
    return [FinancePerDealerSummary(**r) for r in rows]


@router.get(
    "/activity",
    response_model=FinanceActivityPage,
    summary="Get recent finance activity feed",
    description=(
        "Return a paginated unified activity feed across stock entries, credits, and payments.\n\n"
        "Ordered by most recent first."
    ),
    operation_id="finance_activity_feed",
)
# PUBLIC_INTERFACE
def get_finance_activity(
    limit: int = Query(25, ge=1, le=200, description="Max number of activity items to return"),
    offset: int = Query(0, ge=0, description="Number of activity items to skip"),
    db: Session = Depends(get_db),
) -> FinanceActivityPage:
    """Get recent finance activity.

    Args:
        limit: Max number of rows to return (1..200).
        offset: Number of rows to skip.
        db: SQLAlchemy Session dependency.

    Returns:
        FinanceActivityPage: Page of activity items.
    """
    items = list_finance_activity(db, limit=limit, offset=offset)
    return FinanceActivityPage(
        items=[FinanceActivityItem(**it) for it in items],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/summary",
    summary="Get finance dashboard summary",
    description=(
        "Dashboard-friendly finance summary.\n\n"
        "This endpoint exists to satisfy the current frontend hook `useFinanceSummary`, "
        "which calls `GET /finance/summary`.\n\n"
        "It returns a stable shape with nested totals/outstanding/charts and a lastUpdated timestamp."
    ),
    operation_id="finance_dashboard_summary",
)
# PUBLIC_INTERFACE
def get_finance_summary(db: Session = Depends(get_db)) -> dict:
    """Get finance dashboard summary payload.

    Notes on mapping to UI:
      - UI expects: { currency, totals, outstanding, charts, lastUpdated }
      - The UI computes netPosition if missing, but we provide it.

    Args:
        db: SQLAlchemy Session dependency.

    Returns:
        dict: Dashboard summary payload.
    """
    totals = compute_finance_totals(db)

    # Map backend totals to current UI vocabulary.
    total_assets = totals["totalStockValue"]
    total_receivables = totals["totalPayments"]  # simplistic placeholder meaning "inflows tracked"
    total_payables = totals["totalCredits"]  # simplistic placeholder meaning "outflows owed"
    net_position = (Decimal(total_assets) + Decimal(total_receivables) - Decimal(total_payables)).quantize(
        Decimal("0.01")
    )

    # Outstanding: we interpret "unpaidAmount" as outstandingBalance.
    # unpaidCount is derived from per-dealer summaries.
    dealer_summaries = list_finance_per_dealer_summaries(db, limit=200, offset=0)
    unpaid_count = sum(int(d.get("unpaidCount", 0)) for d in dealer_summaries)

    return {
        "currency": "USD",
        "totals": {
            "totalAssets": float(total_assets),
            "totalReceivables": float(total_receivables),
            "totalPayables": float(total_payables),
            "netPosition": float(net_position),
        },
        "outstanding": {
            "unpaidCount": int(unpaid_count),
            "unpaidAmount": float(totals["outstandingBalance"]),
            # Minimal implementation (real implementation would filter payments by month)
            "paidThisMonth": float(0),
        },
        # Include per-dealer rows so the UI/E2E flow can validate balances without
        # making an extra call to /finance/dealers.
        "perDealer": [FinancePerDealerSummary(**r).model_dump() for r in dealer_summaries],
        # Charts are optional; keeping empty arrays lets UI render its placeholders.
        "charts": {"cashflow": [], "outstandingByBucket": []},
        "lastUpdated": _iso_now(),
    }
