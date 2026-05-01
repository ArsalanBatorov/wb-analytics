"""
API endpoints для фактической маржи (кассовый метод).

Источник данных: realization_daily_stats (тот же отчёт, что у финотчёта WB).
Логика расчёта: app/services/margin_fact.py

Все суммы возвращаются в рублях (float). Даты — ISO формат YYYY-MM-DD.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query, HTTPException

from app.services.margin_fact import (
    calc_margin_for_day,
    calc_margin_for_period,
    calc_margin_summary,
)

# Префикс /margin — фронт будет звать /api/margin/... через nginx-проксирование
router = APIRouter(prefix="/margin", tags=["margin"])


def _resolve_period(
    date_from: date | None,
    date_to: date | None,
    default_days: int = 30,
) -> tuple[date, date]:
    """
    Универсальный резолвер периода.
    - Если date_to не задан — берём сегодня.
    - Если date_from не задан — берём date_to минус default_days.
    - Если перепутаны местами — меняем.
    """
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=default_days))
    if start > end:
        start, end = end, start
    return start, end


@router.get("/summary")
async def margin_summary(
    date_from: date | None = Query(default=None, description="Начало периода (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Конец периода (YYYY-MM-DD)"),
):
    """
    KPI-сводка за период (для верхних карточек на дашборде).
    Возвращает выручку, возвраты, логистику, COGS, рекламу, маржу и маржу%.
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)
    try:
        data = await calc_margin_summary(start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта summary: {e}")

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "period_days": (end - start).days + 1,
        "summary": data,
    }


@router.get("/daily")
async def margin_daily(
    date_from: date | None = Query(default=None, description="Начало периода (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Конец периода (YYYY-MM-DD)"),
):
    """
    Маржа по дням (для графика).
    Возвращает массив [{date, revenue, margin, margin_pct, ...}, ...].
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)
    try:
        rows = await calc_margin_for_period(start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта daily: {e}")

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "period_days": (end - start).days + 1,
        "rows_count": len(rows),
        "rows": rows,
    }


@router.get("/products")
async def margin_products(
    date_from: date | None = Query(default=None, description="Начало периода (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Конец периода (YYYY-MM-DD)"),
):
    """
    Маржа по каждому SKU за период (для таблицы товаров).
    Агрегирует calc_margin_for_day по nm_id за весь период.
    Возвращает массив [{nm_id, vendor_code, revenue, margin, margin_pct, ...}, ...]
    отсортированный по марже (худшие сверху).
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)

    # Аккумулируем по nm_id за каждый день периода
    acc: dict[int, dict] = {}
    cur = start
    try:
        while cur <= end:
            day_rows = await calc_margin_for_day(cur, nm_id=None)
            for r in day_rows:
                nm = r["nm_id"]
                if nm not in acc:
                    acc[nm] = {
                        "nm_id": nm,
                        "vendor_code": r.get("vendor_code", ""),
                        "sales_count": 0,
                        "returns_count": 0,
                        "revenue": 0.0,
                        "returns_amount": 0.0,
                        "logistics": 0.0,
                        "storage": 0.0,
                        "deduction": 0.0,
                        "penalty": 0.0,
                        "acquiring": 0.0,
                        "commission": 0.0,
                        "net_payout": 0.0,
                        "cogs": 0.0,
                        "ad_spend": 0.0,
                        "margin": 0.0,
                    }
                a = acc[nm]
                a["sales_count"]    += r.get("sales_count", 0) or 0
                a["returns_count"]  += r.get("returns_count", 0) or 0
                a["revenue"]        += r.get("revenue", 0.0) or 0.0
                a["returns_amount"] += r.get("returns_amount", 0.0) or 0.0
                a["logistics"]      += r.get("logistics", 0.0) or 0.0
                a["storage"]        += r.get("storage", 0.0) or 0.0
                a["deduction"]      += r.get("deduction", 0.0) or 0.0
                a["penalty"]        += r.get("penalty", 0.0) or 0.0
                a["acquiring"]      += r.get("acquiring", 0.0) or 0.0
                a["commission"]     += r.get("commission", 0.0) or 0.0
                a["net_payout"]     += r.get("net_payout", 0.0) or 0.0
                a["cogs"]           += r.get("cogs", 0.0) or 0.0
                a["ad_spend"]       += r.get("ad_spend", 0.0) or 0.0
                a["margin"]         += r.get("margin", 0.0) or 0.0
            cur += timedelta(days=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта products: {e}")

    # Считаем margin_pct и сортируем по марже (худшие сверху)
    products = []
    for nm, a in acc.items():
        rev = a["revenue"]
        a["margin_pct"] = round((a["margin"] / rev * 100), 2) if rev else 0.0
        # Округляем все суммы до 2 знаков для читаемости
        for k, v in a.items():
            if isinstance(v, float):
                a[k] = round(v, 2)
        products.append(a)
    products.sort(key=lambda x: x["margin"])  # худшие сверху

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "period_days": (end - start).days + 1,
        "products_count": len(products),
        "products": products,
    }
