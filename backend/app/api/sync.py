"""
Sync trigger endpoints.
"""
from datetime import date
from fastapi import APIRouter, BackgroundTasks

from app.services.data_sync import (
    full_sync,
    sync_products_and_dimensions,
    sync_stocks,
    sync_daily_stats,
    sync_ad_stats,
    sync_realization_daily,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/full")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    days: int = 7,
    date_from: date | None = None,
    date_to: date | None = None,
):
    background_tasks.add_task(full_sync, days, date_from, date_to)
    return {"status": "sync started", "days": days, "date_from": date_from, "date_to": date_to}


@router.post("/products")
async def trigger_product_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_products_and_dimensions)
    return {"status": "product sync started"}


@router.post("/stocks")
async def trigger_stock_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_stocks)
    return {"status": "stock sync started"}


@router.post("/stats")
async def trigger_stats_sync(
    background_tasks: BackgroundTasks,
    days: int = 7,
    date_from: date | None = None,
    date_to: date | None = None,
):
    background_tasks.add_task(sync_daily_stats, days, date_from, date_to)
    return {"status": "stats sync started", "days": days, "date_from": date_from, "date_to": date_to}


@router.post("/ads")
async def trigger_ad_sync(
    background_tasks: BackgroundTasks,
    days: int = 7,
    date_from: date | None = None,
    date_to: date | None = None,
):
    background_tasks.add_task(sync_ad_stats, days, date_from, date_to)
    return {"status": "ad sync started", "days": days, "date_from": date_from, "date_to": date_to}


@router.post("/realization")
async def trigger_realization_sync(
    background_tasks: BackgroundTasks,
    date_from: date,
    date_to: date,
):
    background_tasks.add_task(sync_realization_daily, date_from, date_to)
    return {"status": "realization sync started", "date_from": date_from, "date_to": date_to}
