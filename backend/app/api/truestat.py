from datetime import date, timedelta
from fastapi import APIRouter, Query, HTTPException

from app.database import async_session
from app.services.truestat import calc_dashboard

router = APIRouter(prefix="/truestat", tags=["truestat"])


def _resolve_period(
    date_from: date | None,
    date_to: date | None,
    default_days: int = 7,
) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=default_days - 1))
    if start > end:
        start, end = end, start
    return start, end


@router.get("/dashboard")
async def truestat_dashboard(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(date_from, date_to, default_days=7)
    try:
        async with async_session() as db:
            return await calc_dashboard(db, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Truestat error: {e}")
