"""
API endpoints для фактической маржи (кассовый метод).

Источник данных: realization_daily_stats (тот же отчёт, что у финотчёта WB).
Логика расчёта: app/services/margin_fact.py
  - calc_margin_for_day(db, target_date, nm_id=None)   → list[dict]
  - calc_margin_for_period(db, date_from, date_to, …)  → list[dict] (по дням × nm_id)
  - calc_margin_summary(db, date_from, date_to, …)     → dict (агрегат)

Все функции принимают AsyncSession первым аргументом — открываем её через
async_session() в каждом endpoint.

Даты в URL — ISO формат YYYY-MM-DD. Все суммы в рублях (float).
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query, HTTPException

from app.database import async_session
from app.services.margin_fact import (
    calc_margin_for_day,
    calc_margin_for_period,
    calc_margin_summary,
)

router = APIRouter(prefix="/margin", tags=["margin"])


def _resolve_period(
    date_from: date | None,
    date_to: date | None,
    default_days: int = 30,
) -> tuple[date, date]:
    """
    Универсальный резолвер периода:
    - если date_to не задан — берём сегодня;
    - если date_from не задан — берём date_to минус default_days;
    - если перепутаны местами — меняем.
    """
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=default_days))
    if start > end:
        start, end = end, start
    return start, end


@router.get("/summary")
async def margin_summary(
    date_from: date | None = Query(default=None, description="Начало периода YYYY-MM-DD"),
    date_to:   date | None = Query(default=None, description="Конец периода YYYY-MM-DD"),
    nm_id:     int | None  = Query(default=None, description="Опц. фильтр по одному SKU"),
):
    """
    KPI-сводка за период (для верхних карточек дашборда).
    Один dict со всеми итогами: revenue, margin, margin_pct, logistics, cogs, ad_spend и т.д.
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)
    try:
        async with async_session() as db:
            data = await calc_margin_summary(db, start, end, nm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта summary: {e}")

    # date в JSON: явно сериализуем (Pydantic это сделает, но на всякий)
    data["date_from"] = start.isoformat()
    data["date_to"]   = end.isoformat()
    return {
        "date_from":   start.isoformat(),
        "date_to":     end.isoformat(),
        "period_days": (end - start).days + 1,
        "summary":     data,
    }


@router.get("/daily")
async def margin_daily(
    date_from: date | None = Query(default=None, description="Начало периода YYYY-MM-DD"),
    date_to:   date | None = Query(default=None, description="Конец периода YYYY-MM-DD"),
    nm_id:     int | None  = Query(default=None, description="Опц. фильтр по одному SKU"),
):
    """
    Маржа по дням за период.
    Возвращает массив строк (по одной на каждый день × nm_id).
    Для общего графика «маржа по дням» фронт должен агрегировать
    sum(margin) GROUP BY date.
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)
    try:
        async with async_session() as db:
            rows = await calc_margin_for_period(db, start, end, nm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта daily: {e}")

    # Дополнительно агрегируем по дате — это то, что нужно графику.
    # rows = [{date, nm_id, sales_revenue, margin, ...}, ...]
    by_day: dict[str, dict] = {}
    for r in rows:
        d = r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"])
        if d not in by_day:
            by_day[d] = {
                "date":          d,
                "sales_count":   0,
                "returns_count": 0,
                "sales_revenue": 0.0,
                "logistics":     0.0,
                "storage":       0.0,
                "deduction":     0.0,
                "cogs":          0.0,
                "ad_spend":      0.0,
                "net_payout":    0.0,
                "margin":        0.0,
            }
        b = by_day[d]
        b["sales_count"]   += r.get("sales_count", 0) or 0
        b["returns_count"] += r.get("returns_count", 0) or 0
        b["sales_revenue"] += r.get("sales_revenue", 0.0) or 0.0
        b["logistics"]     += r.get("logistics", 0.0) or 0.0
        b["storage"]       += r.get("storage", 0.0) or 0.0
        b["deduction"]     += r.get("deduction", 0.0) or 0.0
        b["cogs"]          += r.get("cogs", 0.0) or 0.0
        b["ad_spend"]      += r.get("ad_spend", 0.0) or 0.0
        b["net_payout"]    += r.get("net_payout", 0.0) or 0.0
        b["margin"]        += r.get("margin", 0.0) or 0.0

    # Считаем margin_pct и округляем
    daily = []
    for d in sorted(by_day.keys()):
        b = by_day[d]
        rev = b["sales_revenue"]
        b["margin_pct"] = round((b["margin"] / rev * 100), 2) if rev > 0 else 0.0
        for k, v in b.items():
            if isinstance(v, float):
                b[k] = round(v, 2)
        daily.append(b)

    return {
        "date_from":   start.isoformat(),
        "date_to":     end.isoformat(),
        "period_days": (end - start).days + 1,
        "rows_count":  len(daily),
        "rows":        daily,
        # Сырые строки (день × nm_id) — пригодятся для drill-down в будущем
        "raw_count":   len(rows),
    }


@router.get("/products")
async def margin_products(
    date_from: date | None = Query(default=None, description="Начало периода YYYY-MM-DD"),
    date_to:   date | None = Query(default=None, description="Конец периода YYYY-MM-DD"),
):
    """
    Маржа по каждому SKU за период (для таблицы товаров).
    Берём calc_margin_for_period (день × nm_id) и схлопываем по nm_id.
    Сортировка: худшие сверху (margin asc).
    """
    start, end = _resolve_period(date_from, date_to, default_days=30)

    try:
        async with async_session() as db:
            rows = await calc_margin_for_period(db, start, end, nm_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта products: {e}")

    # Аккумулируем по nm_id
    acc: dict[int, dict] = {}
    for r in rows:
        nm = r["nm_id"]
        if nm not in acc:
            acc[nm] = {
                "nm_id":           nm,
                "sales_count":     0,
                "returns_count":   0,
                "net_qty":         0,
                "sales_revenue":   0.0,
                "returns_revenue": 0.0,
                "logistics":       0.0,
                "storage":         0.0,
                "acceptance":      0.0,
                "deduction":       0.0,
                "penalty":         0.0,
                "commission":      0.0,
                "acquiring":       0.0,
                "cogs":            0.0,
                "ad_spend":        0.0,
                "net_payout":      0.0,
                "margin":          0.0,
            }
        a = acc[nm]
        a["sales_count"]     += r.get("sales_count", 0) or 0
        a["returns_count"]   += r.get("returns_count", 0) or 0
        a["net_qty"]         += r.get("net_qty", 0) or 0
        a["sales_revenue"]   += r.get("sales_revenue", 0.0) or 0.0
        a["returns_revenue"] += r.get("returns_revenue", 0.0) or 0.0
        a["logistics"]       += r.get("logistics", 0.0) or 0.0
        a["storage"]         += r.get("storage", 0.0) or 0.0
        a["acceptance"]      += r.get("acceptance", 0.0) or 0.0
        a["deduction"]       += r.get("deduction", 0.0) or 0.0
        a["penalty"]         += r.get("penalty", 0.0) or 0.0
        a["commission"]      += r.get("commission", 0.0) or 0.0
        a["acquiring"]       += r.get("acquiring", 0.0) or 0.0
        a["cogs"]            += r.get("cogs", 0.0) or 0.0
        a["ad_spend"]        += r.get("ad_spend", 0.0) or 0.0
        a["net_payout"]      += r.get("net_payout", 0.0) or 0.0
        a["margin"]          += r.get("margin", 0.0) or 0.0

    # Считаем margin_pct, округляем, сортируем по марже (худшие сверху)
    products = []
    for nm, a in acc.items():
        rev = a["sales_revenue"]
        a["margin_pct"] = round((a["margin"] / rev * 100), 2) if rev > 0 else 0.0
        for k, v in a.items():
            if isinstance(v, float):
                a[k] = round(v, 2)
        products.append(a)
    products.sort(key=lambda x: x["margin"])

    return {
        "date_from":      start.isoformat(),
        "date_to":        end.isoformat(),
        "period_days":    (end - start).days + 1,
        "products_count": len(products),
        "products":       products,
    }
