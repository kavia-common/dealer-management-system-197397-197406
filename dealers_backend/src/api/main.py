from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dealers import router as dealers_router
from src.api.payroll_credits import router as payroll_credits_router
from src.api.stock import router as stock_router
from src.core.config import get_settings
from src.db.session import get_db

settings = get_settings()

openapi_tags = [
    {"name": "Health", "description": "Service and dependency health checks."},
    {"name": "Dealers", "description": "CRUD operations for dealer records."},
    {"name": "Stock", "description": "CRUD operations for stock entries (purchases from dealers)."},
    {"name": "Payroll/Credits", "description": "CRUD operations for dealer payroll credits and balance computation."},
]

app = FastAPI(
    title=settings.app_title,
    description="Backend API for managing dealers, stock entries, payroll credits, payments and reporting.",
    version=settings.app_version,
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(dealers_router, prefix="/api")
app.include_router(stock_router, prefix="/api")
app.include_router(payroll_credits_router, prefix="/api")


@app.get(
    "/",
    tags=["Health"],
    summary="Basic health check",
    description="Returns a simple response indicating the service is running.",
    operation_id="health_check",
)
def health_check():
    """Entrypoint health check.

    Returns:
        dict: Simple message indicating service status.
    """
    return {"message": "Healthy"}


@app.get(
    "/health/db",
    tags=["Health"],
    summary="Database connectivity check",
    description="Runs a simple SELECT 1 against PostgreSQL to verify connectivity.",
    operation_id="health_check_db",
)
def health_check_db(db: Session = Depends(get_db)):
    """Database health check.

    Args:
        db: SQLAlchemy Session dependency.

    Returns:
        dict: Status plus a simple echo value from the DB.
    """
    value = db.execute(text("SELECT 1")).scalar_one()
    return {"database": "ok", "select_1": int(value)}
