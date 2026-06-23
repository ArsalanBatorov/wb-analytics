import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _f(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


async def _load_tax_rate(db: AsyncSession) -> float:
    r = await db.execute(
        text("SELECT value FROM app_settings WHERE key = 'tax_rate'")
    )
    v = r.scalar_one_or_none()
    return float(v) if v else 7.0


async def _period_data(db: AsyncSession, dfrom: date, dto: date) -> dict:
    sql = """
    WITH rds AS (
        SELECT
            COALESCE(SUM(sales_count), 0) AS sales_count,
            COALESCE(SUM(sales_revenue), 0) AS sales_revenue,
            COALESCE(SUM(returns_count), 0) AS returns_count,
            COALESCE(SUM(returns_revenue), 0) AS returns_revenue,
            COALESCE(SUM(logistics_cost + rebill_logistics_cost), 0) AS logistics,
            COALESCE(SUM(storage_cost), 0) AS storage,
            COALESCE(SUM(acceptance_cost), 0) AS acceptance,
            COALESCE(SUM(deduction_cost), 0) AS deduction,
            COALESCE(SUM(penalty_cost), 0) AS penalty,
            COALESCE(SUM(additional_payment), 0) AS compensation,
            COALESCE(SUM(acquiring_sales + acquiring_returns), 0) AS acquiring,
            COALESCE(SUM(commission_sales - commission_returns), 0) AS commission,
            COALESCE(SUM(net_payout), 0) AS net_payout,
            COALESCE(SUM(cost_price_estimate), 0) AS cogs
        FROM realization_daily_stats
        WHERE stat_date BETWEEN :dfrom AND :dto
    ),
    pds AS (
        SELECT
            COALESCE(SUM(order_count), 0) AS order_count,
            COALESCE(SUM(order_sum), 0) AS order_sum,
            COALESCE(SUM(buyout_count), 0) AS buyout_count,
            COALESCE(SUM(buyout_sum), 0) AS buyout_sum,
            COALESCE(SUM(ad_spend), 0) AS ad_spend,
            COALESCE(AVG(avg_price_before_spp), 0) AS avg_price_before_spp
        FROM product_daily_stats
        WHERE date BETWEEN :dfrom AND :dto
    )
    SELECT * FROM rds, pds
    """
    r = (await db.execute(text(sql), {"dfrom": dfrom, "dto": dto})).mappings().one()
    return {k: _f(r[k]) for k in r.keys()}


def _calc_metrics(d: dict, tax_rate: float, prev: Optional[dict] = None) -> dict:
    sales_rev = d["sales_revenue"]
    sales_cnt = d["sales_count"]
    ret_cnt = d["returns_count"]
    net_payout = d["net_payout"]
    cogs = d["cogs"]
    ad_spend = d["ad_spend"]
    order_cnt = d["order_count"]
    order_sum = d["order_sum"]

    margin = net_payout - cogs - ad_spend
    margin_pct = (margin / sales_rev * 100) if sales_rev > 0 else 0.0
    drr = (ad_spend / sales_rev * 100) if sales_rev > 0 else 0.0
    drr_orders = (ad_spend / order_sum * 100) if order_sum > 0 else 0.0
    buyout_rate = (sales_cnt / (sales_cnt + ret_cnt) * 100) if (sales_cnt + ret_cnt) > 0 else 0.0
    realization = sales_rev
    tax_est = max(0, margin) * tax_rate / 100.0
    avg_sale_price = (sales_rev / sales_cnt) if sales_cnt > 0 else 0.0
    avg_logistics_per_item = (d["logistics"] / sales_cnt) if sales_cnt > 0 else 0.0
    commission_pct = (d["commission"] / sales_rev * 100) if sales_rev > 0 else 0.0
    storage_pct = (d["storage"] / sales_rev * 100) if sales_rev > 0 else 0.0
    logistics_pct = (d["logistics"] / sales_rev * 100) if sales_rev > 0 else 0.0
    acceptance_pct = (d["acceptance"] / sales_rev * 100) if sales_rev > 0 else 0.0
    deduction_pct = (d["deduction"] / sales_rev * 100) if sales_rev > 0 else 0.0
    cogs_pct = (cogs / sales_rev * 100) if sales_rev > 0 else 0.0
    penalty_pct = (d["penalty"] / sales_rev * 100) if sales_rev > 0 else 0.0
    compensation_pct = (d["compensation"] / sales_rev * 100) if sales_rev > 0 else 0.0
    tax_pct = (tax_est / sales_rev * 100) if sales_rev > 0 else 0.0

    result = {
        "margin": {"value": round(margin, 2), "value_pct": round(margin_pct, 2)},
        "orders": {"value": round(order_sum, 2), "value_count": int(order_cnt)},
        "sales": {"value": round(sales_rev, 2), "value_count": int(sales_cnt)},
        "ad_spend": {"value": round(ad_spend, 2), "value_pct": round(drr, 2)},
        "net_margin": {"value": round(margin, 2), "value_pct": round(margin_pct, 2)},
        "logistics": {"value": round(d["logistics"], 2), "value_pct": round(logistics_pct, 2)},
        "buyout_rate": {"value_pct": round(buyout_rate, 2)},
        "realization": {"value": round(realization, 2)},
        "storage": {"value": round(d["storage"], 2), "value_pct": round(storage_pct, 2)},
        "acceptance": {"value": round(d["acceptance"], 2), "value_pct": round(acceptance_pct, 2)},
        "deduction": {"value": round(d["deduction"], 2), "value_pct": round(deduction_pct, 2)},
        "roi": {"value_pct": 0.0},
        "cogs": {"value": round(cogs, 2), "value_pct": round(cogs_pct, 2)},
        "operational_expenses": {"value": 0.0, "value_pct": 0.0},
        "taxes": {"value": round(tax_est, 2), "value_pct": round(tax_pct, 2)},
        "commission": {"value": round(d["commission"], 2), "value_pct": round(commission_pct, 2)},
        "avg_price_before_discount": {"value": round(d["avg_price_before_spp"], 2)},
        "capitalization_cogs": {"value": 0.0},
        "capitalization_retail": {"value": 0.0},
        "penalty": {"value": round(d["penalty"], 2), "value_pct": round(penalty_pct, 2)},
        "compensation": {"value": round(d["compensation"], 2), "value_pct": round(compensation_pct, 2)},
        "avg_sale_price": {"value": round(avg_sale_price, 2)},
        "drr_orders": {"value": round(ad_spend, 2), "value_pct": round(drr_orders, 2)},
        "avg_logistics_per_item": {"value": round(avg_logistics_per_item, 2)},
        "turnover_days_sales": {"value": 0.0},
        "turnover_days_orders": {"value": 0.0},
    }

    if prev:
        prev_metrics = _calc_metrics(prev, tax_rate)
        delta_abs = {}
        delta_pct = {}
        for key in result:
            cv = result[key]
            pv = prev_metrics[key]
            c_main = cv.get("value", cv.get("value_pct", 0))
            p_main = pv.get("value", pv.get("value_pct", 0))
            delta_abs[key] = round(c_main - p_main, 2)
            delta_pct[key] = round((c_main - p_main) / abs(p_main) * 100, 2) if abs(p_main) > 0.001 else 0.0
        result["_delta_abs"] = delta_abs
        result["_delta_pct"] = delta_pct
        result["_prev"] = prev_metrics

    return result


async def calc_dashboard(
    db: AsyncSession,
    date_from: date,
    date_to: date,
) -> dict:
    period_len = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=period_len - 1)

    curr_raw = await _period_data(db, date_from, date_to)
    prev_raw = await _period_data(db, prev_from, prev_to)
    tax_rate = await _load_tax_rate(db)

    curr = _calc_metrics(curr_raw, tax_rate)
    prev = _calc_metrics(prev_raw, tax_rate)
    full = _calc_metrics(curr_raw, tax_rate, prev_raw)

    return {
        "period": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "days": period_len,
        },
        "prev_period": {
            "date_from": prev_from.isoformat(),
            "date_to": prev_to.isoformat(),
            "days": period_len,
        },
        "metrics": full,
    }
