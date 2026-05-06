"""
Расчёт План/Факт по расчётным данным (product_daily_stats).

В отличие от margin_fact.py (источник realization_daily_stats — фактический
финотчёт с задержкой 7-14 дней), здесь источник product_daily_stats —
расчётная маржа из ежедневного синка WB API. Задержка 1-2 дня.

Используется на странице «План/Факт» для оперативного контроля выполнения
плана: сравнение факта с планом + прогноз до конца месяца.
"""

import calendar
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import ProductDailyStat, Product
from app.models.monthly_plan import MonthlyPlan


def _f(v) -> float:
    """Безопасное преобразование Decimal/None/int → float."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


async def get_monthly_plan(db: AsyncSession, month: date) -> dict:
    """
    Получить план месяца. Если плана нет — вернуть нули.
    month — первый день месяца (например, 2026-05-01).
    """
    q = select(MonthlyPlan).where(MonthlyPlan.month == month)
    res = await db.execute(q)
    plan = res.scalar_one_or_none()
    if plan is None:
        return {
            "month": month.isoformat(),
            "plan_orders_qty": 0,
            "plan_orders_revenue": 0.0,
            "plan_buyouts_qty": 0,
            "plan_buyouts_revenue": 0.0,
            "plan_margin": 0.0,
            "exists": False,
        }
    return {
        "month": plan.month.isoformat(),
        "plan_orders_qty": plan.plan_orders_qty,
        "plan_orders_revenue": _f(plan.plan_orders_revenue),
        "plan_buyouts_qty": plan.plan_buyouts_qty,
        "plan_buyouts_revenue": _f(plan.plan_buyouts_revenue),
        "plan_margin": _f(plan.plan_margin),
        "exists": True,
    }


async def upsert_monthly_plan(db: AsyncSession, month: date, data: dict) -> dict:
    """
    Создать или обновить план месяца. Возвращает обновлённый план.
    data: {plan_orders_qty, plan_orders_revenue, plan_buyouts_qty,
           plan_buyouts_revenue, plan_margin}
    """
    q = select(MonthlyPlan).where(MonthlyPlan.month == month)
    res = await db.execute(q)
    plan = res.scalar_one_or_none()

    if plan is None:
        plan = MonthlyPlan(month=month)
        db.add(plan)

    plan.plan_orders_qty = int(data.get("plan_orders_qty", 0) or 0)
    plan.plan_orders_revenue = Decimal(str(data.get("plan_orders_revenue", 0) or 0))
    plan.plan_buyouts_qty = int(data.get("plan_buyouts_qty", 0) or 0)
    plan.plan_buyouts_revenue = Decimal(str(data.get("plan_buyouts_revenue", 0) or 0))
    plan.plan_margin = Decimal(str(data.get("plan_margin", 0) or 0))

    await db.commit()
    await db.refresh(plan)

    return {
        "month": plan.month.isoformat(),
        "plan_orders_qty": plan.plan_orders_qty,
        "plan_orders_revenue": _f(plan.plan_orders_revenue),
        "plan_buyouts_qty": plan.plan_buyouts_qty,
        "plan_buyouts_revenue": _f(plan.plan_buyouts_revenue),
        "plan_margin": _f(plan.plan_margin),
        "exists": True,
    }


async def calc_fact_for_period(db: AsyncSession, date_from: date, date_to: date) -> dict:
    """
    Агрегация факта из product_daily_stats за период.
    Возвращает суммы и количество дней с данными.
    """
    q = select(
        func.coalesce(func.sum(ProductDailyStat.order_count), 0).label("orders_qty"),
        func.coalesce(func.sum(ProductDailyStat.order_sum), 0.0).label("orders_revenue"),
        func.coalesce(func.sum(ProductDailyStat.buyout_count), 0).label("buyouts_qty"),
        func.coalesce(func.sum(ProductDailyStat.buyout_sum), 0.0).label("buyouts_revenue"),
        func.coalesce(func.sum(ProductDailyStat.margin_profit), 0.0).label("margin"),
        func.coalesce(func.sum(ProductDailyStat.ad_spend), 0.0).label("ad_spend"),
        func.count(func.distinct(ProductDailyStat.date)).label("days_with_data"),
    ).where(
        ProductDailyStat.date >= date_from,
        ProductDailyStat.date <= date_to,
    )
    res = await db.execute(q)
    row = res.one()

    return {
        "orders_qty": int(row.orders_qty or 0),
        "orders_revenue": _f(row.orders_revenue),
        "buyouts_qty": int(row.buyouts_qty or 0),
        "buyouts_revenue": _f(row.buyouts_revenue),
        "margin": _f(row.margin),
        "ad_spend": _f(row.ad_spend),
        "days_with_data": int(row.days_with_data or 0),
    }


async def calc_plan_fact_summary(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    plan_month: date,
) -> dict:
    """
    Главная функция — собирает матрицу План/Факт.

    plan_month — первый день месяца, для которого взят план.
    date_from..date_to — период для факта (может быть короче месяца, например
    «Тек. месяц» с 1-го по сегодня, или «7 дней» — последние 7 дней).
    """
    plan = await get_monthly_plan(db, plan_month)
    fact = await calc_fact_for_period(db, date_from, date_to)

    days_in_month = _days_in_month(plan_month)
    period_days = (date_to - date_from).days + 1
    fact_days = fact["days_with_data"] or period_days  # если нет данных — нулевой прогноз

    # План в среднем за день — по плану на месяц
    plan_per_day_orders_qty = plan["plan_orders_qty"] / days_in_month if days_in_month else 0
    plan_per_day_orders_revenue = plan["plan_orders_revenue"] / days_in_month if days_in_month else 0
    plan_per_day_buyouts_qty = plan["plan_buyouts_qty"] / days_in_month if days_in_month else 0
    plan_per_day_buyouts_revenue = plan["plan_buyouts_revenue"] / days_in_month if days_in_month else 0
    plan_per_day_margin = plan["plan_margin"] / days_in_month if days_in_month else 0

    # Факт в среднем за день — по числу дней с данными
    def _avg(total, days):
        return (total / days) if days else 0

    fact_per_day_orders_qty = _avg(fact["orders_qty"], fact_days)
    fact_per_day_orders_revenue = _avg(fact["orders_revenue"], fact_days)
    fact_per_day_buyouts_qty = _avg(fact["buyouts_qty"], fact_days)
    fact_per_day_buyouts_revenue = _avg(fact["buyouts_revenue"], fact_days)
    fact_per_day_margin = _avg(fact["margin"], fact_days)

    # Прогноз на месяц = факт_ср/день × дней_в_месяце
    forecast_orders_qty = fact_per_day_orders_qty * days_in_month
    forecast_orders_revenue = fact_per_day_orders_revenue * days_in_month
    forecast_buyouts_qty = fact_per_day_buyouts_qty * days_in_month
    forecast_buyouts_revenue = fact_per_day_buyouts_revenue * days_in_month
    forecast_margin = fact_per_day_margin * days_in_month

    # ДРР справочно: ad_spend / orders_revenue × 100
    drr = (fact["ad_spend"] / fact["buyouts_revenue"] * 100) if fact["buyouts_revenue"] else 0

    def _pct(fact_v, plan_v):
        return (fact_v / plan_v * 100) if plan_v else 0

    metrics = [
        {
            "key": "orders_revenue",
            "title": "Заказы, ₽",
            "plan_per_day": round(plan_per_day_orders_revenue, 2),
            "fact_per_day": round(fact_per_day_orders_revenue, 2),
            "forecast": round(forecast_orders_revenue, 2),
            "plan_total": round(plan["plan_orders_revenue"], 2),
            "fact_total": round(fact["orders_revenue"], 2),
            "pct": round(_pct(fact["orders_revenue"], plan["plan_orders_revenue"]), 1),
        },
        {
            "key": "buyouts_revenue",
            "title": "Выкупы, ₽",
            "plan_per_day": round(plan_per_day_buyouts_revenue, 2),
            "fact_per_day": round(fact_per_day_buyouts_revenue, 2),
            "forecast": round(forecast_buyouts_revenue, 2),
            "plan_total": round(plan["plan_buyouts_revenue"], 2),
            "fact_total": round(fact["buyouts_revenue"], 2),
            "pct": round(_pct(fact["buyouts_revenue"], plan["plan_buyouts_revenue"]), 1),
        },
        {
            "key": "orders_qty",
            "title": "Заказы, шт",
            "plan_per_day": round(plan_per_day_orders_qty, 2),
            "fact_per_day": round(fact_per_day_orders_qty, 2),
            "forecast": round(forecast_orders_qty, 0),
            "plan_total": plan["plan_orders_qty"],
            "fact_total": fact["orders_qty"],
            "pct": round(_pct(fact["orders_qty"], plan["plan_orders_qty"]), 1),
        },
        {
            "key": "buyouts_qty",
            "title": "Выкупы, шт",
            "plan_per_day": round(plan_per_day_buyouts_qty, 2),
            "fact_per_day": round(fact_per_day_buyouts_qty, 2),
            "forecast": round(forecast_buyouts_qty, 0),
            "plan_total": plan["plan_buyouts_qty"],
            "fact_total": fact["buyouts_qty"],
            "pct": round(_pct(fact["buyouts_qty"], plan["plan_buyouts_qty"]), 1),
        },
        {
            "key": "margin",
            "title": "Валовая прибыль, ₽",
            "plan_per_day": round(plan_per_day_margin, 2),
            "fact_per_day": round(fact_per_day_margin, 2),
            "forecast": round(forecast_margin, 2),
            "plan_total": round(plan["plan_margin"], 2),
            "fact_total": round(fact["margin"], 2),
            "pct": round(_pct(fact["margin"], plan["plan_margin"]), 1),
        },
        {
            "key": "drr",
            "title": "ДРР, %",
            "plan_per_day": None,
            "fact_per_day": round(drr, 2),
            "forecast": round(drr, 2),
            "plan_total": None,
            "fact_total": round(drr, 2),
            "pct": None,
        },
    ]

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "plan_month": plan_month.isoformat(),
        "days_in_month": days_in_month,
        "period_days": period_days,
        "fact_days": fact_days,
        "plan": plan,
        "fact": fact,
        "metrics": metrics,
    }


async def calc_plan_fact_products(
    db: AsyncSession,
    date_from: date,
    date_to: date,
) -> list:
    """
    Таблица SKU из product_daily_stats за период.
    Агрегация по nm_id + JOIN с products для vendor_code и title.
    """
    q = (
        select(
            ProductDailyStat.nm_id,
            Product.vendor_code,
            Product.title,
            func.coalesce(func.sum(ProductDailyStat.order_count), 0).label("orders_qty"),
            func.coalesce(func.sum(ProductDailyStat.order_sum), 0.0).label("orders_revenue"),
            func.coalesce(func.sum(ProductDailyStat.buyout_count), 0).label("buyouts_qty"),
            func.coalesce(func.sum(ProductDailyStat.buyout_sum), 0.0).label("buyouts_revenue"),
            func.coalesce(func.sum(ProductDailyStat.margin_profit), 0.0).label("margin"),
            func.coalesce(func.sum(ProductDailyStat.ad_spend), 0.0).label("ad_spend"),
        )
        .outerjoin(Product, Product.nm_id == ProductDailyStat.nm_id)
        .where(
            ProductDailyStat.date >= date_from,
            ProductDailyStat.date <= date_to,
        )
        .group_by(ProductDailyStat.nm_id, Product.vendor_code, Product.title)
        .order_by(func.sum(ProductDailyStat.margin_profit).asc())
    )
    res = await db.execute(q)
    rows = res.all()

    out = []
    for r in rows:
        orders_revenue = _f(r.orders_revenue)
        buyouts_revenue = _f(r.buyouts_revenue)
        ad_spend = _f(r.ad_spend)
        drr = (ad_spend / buyouts_revenue * 100) if buyouts_revenue else 0
        out.append({
            "nm_id": r.nm_id,
            "vendor_code": r.vendor_code or "",
            "title": r.title or "",
            "orders_qty": int(r.orders_qty or 0),
            "orders_revenue": round(orders_revenue, 2),
            "buyouts_qty": int(r.buyouts_qty or 0),
            "buyouts_revenue": round(_f(r.buyouts_revenue), 2),
            "margin": round(_f(r.margin), 2),
            "ad_spend": round(ad_spend, 2),
            "drr": round(drr, 2),
        })
    return out
