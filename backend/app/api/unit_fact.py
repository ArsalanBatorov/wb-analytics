import logging
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/truestat", tags=["unit_fact"])


def _to_float(v, default=0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, Decimal):
        return round(float(v), 2)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".").replace("₽", "").replace("%", "")
    if not s or s == "-":
        return default
    try:
        return round(float(s), 2)
    except ValueError:
        return default


def _to_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if not s or s == "-":
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


@router.get("/unit-fact")
async def get_unit_fact(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    where_rd = ""
    params = {}

    if date_from:
        where_rd += " AND rd.stat_date >= :df"
        params["df"] = date.fromisoformat(date_from)
    if date_to:
        where_rd += " AND rd.stat_date <= :dt"
        params["dt"] = date.fromisoformat(date_to)

    r = await db.execute(text(f"""
        SELECT
            p.nm_id,
            p.vendor_code,
            p.cost_price,
            COALESCE(SUM(rd.sales_count), 0) as sales_count,
            COALESCE(SUM(rd.returns_count), 0) as returns_count,
            COALESCE(SUM(rd.sales_revenue), 0) as sales_revenue,
            COALESCE(SUM(rd.returns_revenue), 0) as returns_revenue,
            COALESCE(SUM(rd.logistics_cost), 0) as logistics_cost,
            COALESCE(SUM(rd.rebill_logistics_cost), 0) as rebill_logistics_cost,
            COALESCE(SUM(rd.storage_cost), 0) as storage_cost,
            COALESCE(SUM(rd.acceptance_cost), 0) as acceptance_cost,
            COALESCE(SUM(rd.deduction_cost), 0) as deduction_cost,
            COALESCE(SUM(rd.penalty_cost), 0) as penalty_cost,
            COALESCE(SUM(rd.additional_payment), 0) as additional_payment,
            COALESCE(SUM(rd.acquiring_sales + rd.acquiring_returns), 0) as acquiring_total,
            COALESCE(SUM(rd.commission_sales + rd.commission_returns), 0) as commission_total,
            COALESCE(SUM(rd.net_payout), 0) as net_payout
        FROM products p
        LEFT JOIN realization_daily_stats rd ON rd.nm_id = p.nm_id
        WHERE 1=1 {where_rd}
        GROUP BY p.nm_id, p.vendor_code, p.cost_price
    """), params)
    realization_rows = {r.nm_id: r for r in r.fetchall()}

    where_pds = ""
    if date_from:
        where_pds += " AND date >= :df2"
        params["df2"] = date.fromisoformat(date_from)
    if date_to:
        where_pds += " AND date <= :dt2"
        params["dt2"] = date.fromisoformat(date_to)

    r2 = await db.execute(text(f"""
        SELECT
            nm_id,
            COALESCE(SUM(ad_spend), 0) as ad_spend_total,
            COALESCE(SUM(order_count), 0) as order_count_total,
            COALESCE(SUM(order_sum), 0) as order_sum_total,
            COALESCE(SUM(buyout_count), 0) as buyout_count_total,
            COALESCE(SUM(buyout_sum), 0) as buyout_sum_total
        FROM product_daily_stats
        WHERE 1=1 {where_pds}
        GROUP BY nm_id
    """), params)
    daily_map = {r.nm_id: r for r in r2.fetchall()}

    r3 = await db.execute(text("""
        SELECT
            nm_id,
            COALESCE(SUM(quantity), 0) as stock_wb,
            COALESCE(SUM(in_way_to_client), 0) as stock_in_transit
        FROM stock_snapshots
        GROUP BY nm_id
    """))
    stock_map = {r.nm_id: r for r in r3.fetchall()}

    rows = []
    for nm_id, rd in realization_rows.items():
        if rd.sales_count == 0 and rd.returns_count == 0 and rd.logistics_cost == 0:
            continue

        pds = daily_map.get(nm_id)
        stk = stock_map.get(nm_id)

        ad_spend = float(pds.ad_spend_total) if pds else 0.0
        order_count = int(pds.order_count_total) if pds else 0
        order_sum = float(pds.order_sum_total) if pds else 0.0
        buyout_count = int(pds.buyout_count_total) if pds else 0
        buyout_sum = float(pds.buyout_sum_total) if pds else 0.0

        stock_wb = int(stk.stock_wb) if stk else 0
        stock_in_transit = int(stk.stock_in_transit) if stk else 0

        sales_count = int(rd.sales_count)
        returns_count = int(rd.returns_count)
        net_sales = sales_count - returns_count
        sales_revenue = float(rd.sales_revenue)
        returns_revenue = float(rd.returns_revenue)
        revenue = sales_revenue - returns_revenue
        cost_price = float(rd.cost_price or 0)

        cost_price_total = cost_price * net_sales
        logistics_cost = float(rd.logistics_cost)
        storage_cost = float(rd.storage_cost)
        logistics_total = logistics_cost + storage_cost
        logistics_return = float(rd.rebill_logistics_cost)
        commission = float(rd.commission_total)
        acquiring_penalty = float(rd.acquiring_total) + float(rd.deduction_cost) + float(rd.penalty_cost)
        net_payout = float(rd.net_payout)
        profit = net_payout - cost_price_total - ad_spend

        returns_pct = round(returns_count / sales_count, 4) if sales_count > 0 else 0.0
        revenue_per_unit = round(revenue / net_sales, 2) if net_sales > 0 else 0.0
        cost_price_per_unit = round(cost_price, 2)
        cost_price_pct = round(cost_price_total / revenue, 4) if revenue > 0 else 0.0
        commission_pct = round(commission / revenue, 4) if revenue > 0 else 0.0
        logistics_per_unit = round(logistics_total / net_sales, 2) if net_sales > 0 else 0.0
        logistics_pct = round(logistics_total / revenue, 4) if revenue > 0 else 0.0
        logistics_direct = round(logistics_cost, 2)
        logistics_direct_pct = round(logistics_cost / revenue, 4) if revenue > 0 else 0.0
        logistics_return_pct = round(logistics_return / revenue, 4) if revenue > 0 else 0.0
        ad_spend_per_unit = round(ad_spend / net_sales, 2) if net_sales > 0 else 0.0
        margin_per_unit = round(profit / net_sales, 2) if net_sales > 0 else 0.0
        margin_pct = round(profit / revenue, 4) if revenue > 0 else 0.0
        roi_val = round(
            profit / (cost_price_total + ad_spend + logistics_total + commission + acquiring_penalty)
            if (cost_price_total + ad_spend + logistics_total + commission + acquiring_penalty) > 0
            else 0.0, 4
        )

        stock_days_val = 0.0
        avg_sales_per_week = 0.0
        turnover_days = 0.0
        if net_sales > 0:
            period_len = 30
            if date_from and date_to:
                d1 = date.fromisoformat(date_from)
                d2 = date.fromisoformat(date_to)
                period_len = max((d2 - d1).days, 1)
            weeks = max(period_len / 7, 1)
            avg_sales_per_week = round(net_sales / weeks, 2)
            if avg_sales_per_week > 0:
                stock_days_val = round(stock_wb / avg_sales_per_week * 7, 1)
                turnover_days = round(stock_wb / max(net_sales / period_len, 0.01), 1)

        vendor_code = str(rd.vendor_code or "")

        rows.append({
            "vendor_code": vendor_code,
            "sales_count": sales_count,
            "returns_count": returns_count,
            "returns_pct": returns_pct,
            "net_sales": net_sales,
            "revenue": round(revenue, 2),
            "revenue_per_unit": revenue_per_unit,
            "cost_price_total": round(cost_price_total, 2),
            "cost_price_per_unit": cost_price_per_unit,
            "cost_price_pct": cost_price_pct,
            "commission": round(commission, 2),
            "commission_pct": commission_pct,
            "logistics_total": round(logistics_total, 2),
            "logistics_per_unit": logistics_per_unit,
            "logistics_pct": logistics_pct,
            "logistics_direct": round(logistics_direct, 2),
            "logistics_direct_pct": logistics_direct_pct,
            "logistics_return": round(logistics_return, 2),
            "logistics_return_pct": logistics_return_pct,
            "acquiring_penalty": round(acquiring_penalty, 2),
            "ad_spend": round(ad_spend, 2),
            "ad_spend_per_unit": ad_spend_per_unit,
            "margin_per_unit": margin_per_unit,
            "margin_pct": margin_pct,
            "roi": roi_val,
            "stock_wb": stock_wb,
            "stock_in_transit": stock_in_transit,
            "stock_days": stock_days_val,
            "avg_sales_per_week": avg_sales_per_week,
            "turnover_days": turnover_days,
        })

    return {"data": rows, "count": len(rows)}
