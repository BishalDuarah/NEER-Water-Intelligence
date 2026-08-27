from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthStatus

settings = get_settings()

APP_VERSION = "0.1.0"

root_router = APIRouter()


@root_router.get("/health", tags=["health"])
def health_root() -> dict[str, str]:
    return {"status": "ok"}


v1_router = APIRouter()


@v1_router.get("/health", response_model=HealthStatus, tags=["health"])
def health_v1(db: Session = Depends(get_db)) -> HealthStatus:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"
    return HealthStatus(
        status="ok" if db_status == "ok" else "degraded",
        version=APP_VERSION,
        environment=settings.environment,
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )
