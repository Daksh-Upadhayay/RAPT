from typing import Annotated

from fastapi import APIRouter, Query

from app.core.db import SessionDep
from app.schemas.metrics import MetricsSummary
from app.services import metrics as metrics_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
async def summary(session: SessionDep, days: Annotated[int, Query(ge=1, le=365)] = 30) -> MetricsSummary:
    """Dashboard aggregates; `days` sets the window of the daily escalation series."""
    return await metrics_service.summary(session, days)
