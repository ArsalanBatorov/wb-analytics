from datetime import date, timedelta, datetime
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database import async_session
from app.models.settings import AppSettings

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _get_settings() -> dict:
    async with async_session() as db:
        from sqlalchemy import select
        r = await db.execute(select(AppSettings))
        return {s.key: s.value for s in r.scalars().all()}


def _resolve_period(days: int, date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or date.today()
    if date_from:
        start = date_from
    else:
        start = end - timedelta(days=days)
    if start > end:
        start, end = end, start
    return start, end


@router.get("/summary")
async def get_summary(
    days: int = Query(default=7, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    period_days = (end - start).days + 1
    settings = await _get_settings()

    ktr_updated = settings.get("ktr_updated_at", "")
    irp_updated = settings.get("irp_updated_at", "")
    ktr_stale = True
    irp_stale = True
    for key, updated in [("ktr", ktr_updated), ("irp", irp_updated)]:
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                if (datetime.now() - dt).days <= 7:
                    if key == "ktr": ktr_stale = False
                    else: irp_stale = False
            except: pass

    async with async_session() as db:
        r = await db.execute(text("""
            SELECT
                COALESCE(SUM(open_count), 0),
                COALESCE(SUM(cart_count), 0),
                COALESCE(SUM(order_count), 0),
                COALESCE(SUM(order_sum), 0),
                COALESCE(SUM(buyout_count), 0),
                COALESCE(SUM(buyout_sum), 0),
                COALESCE(SUM(ad_spend), 0),
                COALESCE(SUM(ad_orders), 0),
                COALESCE(SUM(ad_clicks), 0),
                COALESCE(SUM(ad_views), 0),
                COALESCE(SUM(delivery_cost * order_count), 0),
                COALESCE(SUM(return_cost * order_count), 0),
                COALESCE(SUM(storage_cost), 0),
                COALESCE(SUM(commission_amount), 0),
                COALESCE(SUM(cost_price_total), 0),
                COALESCE(SUM(margin_profit), 0),
                COALESCE(SUM(margin_clean), 0),
                COUNT(DISTINCT nm_id)
            FROM product_daily_stats
            WHERE date >= :start AND date <= :end
        """), {"start": start, "end": end})
        row = r.fetchone()

        revenue = float(row[3] or 0)
        ad_spend = float(row[6] or 0)
        margin_clean = float(row[16] or 0)
        clicks = row[0] or 0
        carts = row[1] or 0
        total_cost = float(row[14] or 0)

        stock_r = await db.execute(
            text("SELECT COALESCE(SUM(quantity + in_way_to_client), 0) FROM stock_snapshots")
        )

        return {
            "period": {"start": start.isoformat(), "end": end.isoformat(), "days": period_days},
            "clicks": clicks, "carts": carts,
            "orders": row[2] or 0, "revenue": round(revenue, 2),
            "buyouts": row[4] or 0, "buyout_revenue": round(float(row[5] or 0), 2),
            "buyout_pct": round((row[4] or 0) / (row[2] or 1) * 100, 1) if (row[2] or 0) > 0 else 0,
            "ad_spend": round(ad_spend, 2), "ad_orders": row[7] or 0,
            "ad_clicks": row[8] or 0, "ad_views": row[9] or 0,
            "total_delivery": round(float(row[10] or 0), 2),
            "total_return_logistics": round(float(row[11] or 0), 2),
            "total_storage": round(float(row[12] or 0), 2),
            "total_commission": round(float(row[13] or 0), 2),
            "total_cost_price": round(total_cost, 2),
            "margin_profit": round(float(row[15] or 0), 2),
            "margin_clean": round(margin_clean, 2),
            "drr": round((ad_spend / revenue * 100) if revenue > 0 else 0, 2),
            "drr_clean": round((ad_spend / margin_clean * 100) if margin_clean > 0 else 0, 2),
            "cr_cart": round((carts / clicks * 100) if clicks > 0 else 0, 2),
            "cr_order": round((row[2] / clicks * 100) if clicks > 0 else 0, 2),
            "roi": round((margin_clean / (total_cost + ad_spend) * 100) if (total_cost + ad_spend) > 0 else 0, 2),
            "product_count": row[17] or 0,
            "total_stock": stock_r.scalar() or 0,
            "settings": {
                "ktr": settings.get("ktr", "1.0"), "irp": settings.get("irp", "0"),
                "tax_rate": settings.get("tax_rate", "7"), "vat_rate": settings.get("vat_rate", "0"),
            },
            "alerts": {"ktr_stale": ktr_stale, "irp_stale": irp_stale}
        }


@router.get("/products")
async def get_products(
    days: int = Query(default=7, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    month_str = end.strftime("%Y-%m")

    async with async_session() as db:
        # Get plans separately
        plan_r = await db.execute(text(
            "SELECT nm_id, plan_orders FROM product_plans WHERE month = :m"
        ), {"m": month_str})
        plans = {row[0]: row[1] for row in plan_r.fetchall()}

        r = await db.execute(text("""
            SELECT
                p.nm_id, p.vendor_code, p.title, p.brand, p.subject_name,
                p.cost_price, p.volume_liters, p.warehouse_name, p.warehouse_coef,
                p.width_cm, p.height_cm, p.length_cm,
                COALESCE(SUM(s.open_count), 0),
                COALESCE(SUM(s.cart_count), 0),
                COALESCE(SUM(s.order_count), 0),
                COALESCE(SUM(s.order_sum), 0),
                COALESCE(SUM(s.buyout_count), 0),
                COALESCE(SUM(s.buyout_sum), 0),
                COALESCE(p.buyout_percent, 0),
                COALESCE(SUM(s.ad_spend), 0),
                COALESCE(SUM(s.ad_orders), 0),
                COALESCE(SUM(s.ad_clicks), 0),
                COALESCE(SUM(s.ad_views), 0),
                COALESCE(SUM(s.delivery_cost * s.order_count), 0),
                COALESCE(SUM(s.return_cost * s.order_count), 0),
                COALESCE(SUM(s.storage_cost), 0),
                COALESCE(SUM(s.commission_amount), 0),
                COALESCE(SUM(s.cost_price_total), 0),
                COALESCE(SUM(s.margin_profit), 0),
                COALESCE(SUM(s.margin_clean), 0),
                COALESCE(AVG(NULLIF(s.margin_profit_pct, 0)), 0),
                COALESCE(AVG(NULLIF(s.margin_clean_pct, 0)), 0),
                COALESCE(AVG(NULLIF(s.roi, 0)), 0),
                COALESCE(AVG(NULLIF(s.profit_per_order, 0)), 0),
                COUNT(s.id),
                COALESCE((SELECT SUM(ss.quantity + ss.in_way_to_client) FROM stock_snapshots ss WHERE ss.nm_id = p.nm_id), 0)
            FROM products p
            LEFT JOIN product_daily_stats s ON s.nm_id = p.nm_id AND s.date >= :start AND s.date <= :end
            GROUP BY p.id
            ORDER BY COALESCE(SUM(s.order_sum), 0) DESC
        """), {"start": start, "end": end})

        rows = r.fetchall()
        products = []
        for row in rows:
            nm_id = row[0]
            orders = row[14] or 0
            revenue = float(row[15] or 0)
            ad_spend = float(row[19] or 0)
            ad_orders = row[20] or 0
            clicks = row[12] or 0
            carts = row[13] or 0
            ad_clicks = row[21] or 0
            ad_views = row[22] or 0
            margin_clean = float(row[29] or 0)
            plan = plans.get(nm_id, 0)
            stat_days = row[34] or 1

            plan_progress = 0
            plan_on_track = None
            if plan > 0:
                expected = plan * end.day / 30
                plan_progress = round(orders / plan * 100, 1)
                plan_on_track = orders >= expected

            products.append({
                "nm_id": nm_id, "vendor_code": row[1], "title": row[2],
                "brand": row[3], "subject": row[4],
                "cost_price": row[5] or 0, "volume_liters": row[6] or 0,
                "warehouse": row[7] or "", "warehouse_coef": row[8] or 1.0,
                "dimensions": {"width": row[9], "height": row[10], "length": row[11]},
                "clicks": clicks, "carts": carts, "orders": orders,
                "revenue": round(revenue, 2),
                "buyouts": row[16] or 0, "buyout_revenue": round(float(row[17] or 0), 2),
                "buyout_pct": round((row[16] or 0) / orders * 100, 1) if orders > 0 else 0,
                "ad_spend": round(ad_spend, 2), "ad_orders": ad_orders,
                "ad_clicks": ad_clicks, "ad_views": ad_views,
                "ad_ctr": round((ad_clicks / ad_views * 100) if ad_views > 0 else 0, 2),
                "cpo": round((ad_spend / ad_orders) if ad_orders > 0 else 0, 2),
                "drr": round((ad_spend / revenue * 100) if revenue > 0 else 0, 2),
                "drr_clean": round((ad_spend / margin_clean * 100) if margin_clean > 0 else 0, 2),
                "total_delivery": round(float(row[23] or 0), 2),
                "total_return": round(float(row[24] or 0), 2),
                "total_storage": round(float(row[25] or 0), 2),
                "total_commission": round(float(row[26] or 0), 2),
                "total_cost": round(float(row[27] or 0), 2),
                "margin_profit": round(float(row[28] or 0), 2),
                "margin_clean": round(margin_clean, 2),
                "margin_profit_pct": round(float(row[30] or 0), 2),
                "margin_clean_pct": round(float(row[31] or 0), 2),
                "roi": round(float(row[32] or 0), 2),
                "profit_per_order": round(float(row[33] or 0), 2),
                "organic_orders": orders - ad_orders,
                "cr_cart": round((carts / clicks * 100) if clicks > 0 else 0, 2),
                "cr_order": round((orders / clicks * 100) if clicks > 0 else 0, 2),
                "orders_per_1000": round((orders / clicks * 1000) if clicks > 0 else 0, 2),
                "stock": row[35] or 0,
                "plan_orders": plan, "plan_progress": plan_progress,
                "plan_on_track": plan_on_track,
            })

        return {"products": products, "total": len(products)}


@router.get("/products/{nm_id}/daily")
async def get_product_daily(
    nm_id: int,
    days: int = Query(default=7, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)

    async with async_session() as db:
        r = await db.execute(text("""
            SELECT date, open_count, cart_count, order_count, order_sum,
                   buyout_count, buyout_sum, buyout_percent,
                   ad_views, ad_clicks, ad_spend, ad_orders, ad_atbs,
                   delivery_cost, return_cost, storage_cost,
                   commission_amount, cost_price_total,
                   margin_profit, margin_profit_pct,
                   margin_clean, margin_clean_pct, roi, profit_per_order
            FROM product_daily_stats
            WHERE nm_id = :nm AND date >= :start AND date <= :end
            ORDER BY date
        """), {"nm": nm_id, "start": start, "end": end})

        return {"nm_id": nm_id, "daily": [
            {
                "date": row[0].isoformat(), "clicks": row[1], "carts": row[2],
                "orders": row[3], "revenue": round(float(row[4] or 0), 2),
                "buyouts": row[5], "buyout_revenue": round(float(row[6] or 0), 2),
                "buyout_pct": row[7],
                "ad_views": row[8], "ad_clicks": row[9],
                "ad_spend": round(float(row[10] or 0), 2),
                "ad_orders": row[11], "ad_atbs": row[12],
                "delivery_cost": round(float(row[13] or 0), 2),
                "return_cost": round(float(row[14] or 0), 2),
                "storage_cost": round(float(row[15] or 0), 2),
                "commission": round(float(row[16] or 0), 2),
                "cost_price": round(float(row[17] or 0), 2),
                "margin_profit": round(float(row[18] or 0), 2),
                "margin_profit_pct": round(float(row[19] or 0), 2),
                "margin_clean": round(float(row[20] or 0), 2),
                "margin_clean_pct": round(float(row[21] or 0), 2),
                "roi": round(float(row[22] or 0), 2),
                "profit_per_order": round(float(row[23] or 0), 2),
            } for row in r.fetchall()
        ]}


@router.get("/daily")
async def get_daily_overall(
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT
                    date,
                    COALESCE(SUM(open_count), 0) AS clicks,
                    COALESCE(SUM(cart_count), 0) AS carts,
                    COALESCE(SUM(order_count), 0) AS orders,
                    COALESCE(SUM(order_sum), 0) AS revenue,
                    COALESCE(SUM(buyout_count), 0) AS buyouts,
                    COALESCE(SUM(buyout_sum), 0) AS buyout_revenue,
                    COALESCE(SUM(ad_spend), 0) AS ad_spend,
                    COALESCE(SUM(margin_clean), 0) AS margin_clean
                FROM product_daily_stats
                WHERE date >= :start AND date <= :end
                GROUP BY date
                ORDER BY date
                """
            ),
            {"start": start, "end": end},
        )
        rows = r.fetchall()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "daily": [
            {
                "date": row[0].isoformat(),
                "clicks": row[1],
                "carts": row[2],
                "orders": row[3],
                "revenue": round(float(row[4] or 0), 2),
                "buyouts": row[5],
                "buyout_revenue": round(float(row[6] or 0), 2),
                "ad_spend": round(float(row[7] or 0), 2),
                "margin_clean": round(float(row[8] or 0), 2),
            }
            for row in rows
        ],
    }


@router.get("/financial-summary")
async def get_financial_summary(
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(sales_count), 0),
                    COALESCE(SUM(sales_revenue), 0),
                    COALESCE(SUM(returns_count), 0),
                    COALESCE(SUM(returns_revenue), 0),
                    COALESCE(SUM(logistics_cost), 0),
                    COALESCE(SUM(rebill_logistics_cost), 0),
                    COALESCE(SUM(storage_cost), 0),
                    COALESCE(SUM(acceptance_cost), 0),
                    COALESCE(SUM(deduction_cost), 0),
                    COALESCE(SUM(penalty_cost), 0),
                    COALESCE(SUM(additional_payment), 0),
                    COALESCE(SUM(acquiring_sales), 0),
                    COALESCE(SUM(acquiring_returns), 0),
                    COALESCE(SUM(commission_sales), 0),
                    COALESCE(SUM(commission_returns), 0),
                    COALESCE(SUM(payout_sales), 0),
                    COALESCE(SUM(payout_returns), 0),
                    COALESCE(SUM(net_payout), 0),
                    COALESCE(SUM(net_qty), 0),
                    COALESCE(SUM(cost_price_estimate), 0),
                    COALESCE(SUM(profit_estimate), 0)
                FROM realization_daily_stats
                WHERE stat_date >= :start AND stat_date <= :end
                """
            ),
            {"start": start, "end": end},
        )
        row = r.fetchone()
    # Get orders from product_daily_stats
        r_orders = await db.execute(
            text("""
                SELECT COALESCE(SUM(order_count), 0), COALESCE(SUM(order_sum), 0)
                FROM product_daily_stats
                WHERE date >= :start AND date <= :end
            """),
            {"start": start, "end": end},
        )
        orow = r_orders.fetchone()
        total_orders = orow[0] or 0
        total_order_sum = round(float(orow[1] or 0), 2)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "order_count": total_orders,
        "order_sum": total_order_sum,
        "sales_count": row[0] or 0,
        "sales_revenue": round(float(row[1] or 0), 2),
        "returns_count": row[2] or 0,
        "returns_revenue": round(float(row[3] or 0), 2),
        "logistics_cost": round(float(row[4] or 0), 2),
        "rebill_logistics_cost": round(float(row[5] or 0), 2),
        "storage_cost": round(float(row[6] or 0), 2),
        "acceptance_cost": round(float(row[7] or 0), 2),
        "deduction_cost": round(float(row[8] or 0), 2),
        "penalty_cost": round(float(row[9] or 0), 2),
        "additional_payment": round(float(row[10] or 0), 2),
        "acquiring_sales": round(float(row[11] or 0), 2),
        "acquiring_returns": round(float(row[12] or 0), 2),
        "commission_sales": round(float(row[13] or 0), 2),
        "commission_returns": round(float(row[14] or 0), 2),
        "payout_sales": round(float(row[15] or 0), 2),
        "payout_returns": round(float(row[16] or 0), 2),
        "net_payout": round(float(row[17] or 0), 2),
        "net_qty": row[18] or 0,
        "cost_price_estimate": round(float(row[19] or 0), 2),
        "profit_estimate": round(float(row[20] or 0), 2),
    }


@router.get("/financial-daily")
async def get_financial_daily(
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT
                    r.stat_date,
                    COALESCE(SUM(r.sales_count), 0),
                    COALESCE(SUM(r.sales_revenue), 0),
                    COALESCE(SUM(r.returns_count), 0),
                    COALESCE(SUM(r.returns_revenue), 0),
                    COALESCE(SUM(r.net_payout), 0),
                    COALESCE(SUM(r.profit_estimate), 0),
                    COALESCE(o.order_count, 0)
                FROM realization_daily_stats r
                LEFT JOIN (
                    SELECT date, SUM(order_count) as order_count
                    FROM product_daily_stats
                    GROUP BY date
                ) o ON o.date = r.stat_date
                WHERE r.stat_date >= :start AND r.stat_date <= :end
                GROUP BY r.stat_date, o.order_count
                ORDER BY r.stat_date
                """
            ),
            {"start": start, "end": end},
        )
        rows = r.fetchall()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "daily": [
            {
                "date": row[0].isoformat(),
                "order_count": row[7] or 0,
                "sales_count": row[1],
                "sales_revenue": round(float(row[2] or 0), 2),
                "returns_count": row[3],
                "returns_revenue": round(float(row[4] or 0), 2),
                "net_payout": round(float(row[5] or 0), 2),
                "profit_estimate": round(float(row[6] or 0), 2),
            }
            for row in rows
        ],
    }


@router.get("/financial-products")
async def get_financial_products(
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT
                    p.nm_id, p.vendor_code, p.title, p.brand,
                    COALESCE(SUM(r.sales_count), 0),
                    COALESCE(SUM(r.sales_revenue), 0),
                    COALESCE(SUM(r.returns_count), 0),
                    COALESCE(SUM(r.returns_revenue), 0),
                    COALESCE(SUM(r.net_payout), 0),
                    COALESCE(SUM(r.profit_estimate), 0),
                    COALESCE(SUM(r.cost_price_estimate), 0),
                    COALESCE(SUM(r.logistics_cost + r.rebill_logistics_cost), 0),
                    COALESCE(SUM(r.storage_cost), 0),
                    COALESCE(o.order_count, 0),
                    COALESCE(o.order_sum, 0)
                FROM products p
                LEFT JOIN realization_daily_stats r
                  ON r.nm_id = p.nm_id AND r.stat_date >= :start AND r.stat_date <= :end
                LEFT JOIN (
                    SELECT nm_id, SUM(order_count) as order_count, SUM(order_sum) as order_sum
                    FROM product_daily_stats
                    WHERE date >= :start AND date <= :end
                    GROUP BY nm_id
                ) o ON o.nm_id = p.nm_id
                GROUP BY p.id, o.order_count, o.order_sum
                ORDER BY COALESCE(SUM(r.sales_revenue), 0) DESC
                """
            ),
            {"start": start, "end": end},
        )
        rows = r.fetchall()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "products": [
            {
                "nm_id": row[0],
                "vendor_code": row[1],
                "title": row[2],
                "brand": row[3],
                "order_count": row[13] or 0,
                "order_sum": round(float(row[14] or 0), 2),
                "sales_count": row[4],
                "sales_revenue": round(float(row[5] or 0), 2),
                "returns_count": row[6],
                "returns_revenue": round(float(row[7] or 0), 2),
                "net_payout": round(float(row[8] or 0), 2),
                "profit_estimate": round(float(row[9] or 0), 2),
                "cost_price_estimate": round(float(row[10] or 0), 2),
                "logistics_cost": round(float(row[11] or 0), 2),
                "storage_cost": round(float(row[12] or 0), 2),
            }
            for row in rows
        ],
    }


@router.get("/financial-products/{nm_id}/daily")
async def get_financial_product_daily(
    nm_id: int,
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT
                    r.stat_date, r.sales_count, r.sales_revenue, r.returns_count, r.returns_revenue,
                    r.net_payout, r.profit_estimate, r.logistics_cost, r.rebill_logistics_cost, r.storage_cost,
                    COALESCE(o.order_count, 0)
                FROM realization_daily_stats r
                LEFT JOIN product_daily_stats o ON o.nm_id = r.nm_id AND o.date = r.stat_date
                WHERE r.nm_id = :nm AND r.stat_date >= :start AND r.stat_date <= :end
                ORDER BY r.stat_date
                """
            ),
            {"nm": nm_id, "start": start, "end": end},
        )
        rows = r.fetchall()
    return {
        "nm_id": nm_id,
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "daily": [
            {
                "date": row[0].isoformat(),
                "order_count": row[10] or 0,
                "sales_count": row[1],
                "sales_revenue": round(float(row[2] or 0), 2),
                "returns_count": row[3],
                "returns_revenue": round(float(row[4] or 0), 2),
                "net_payout": round(float(row[5] or 0), 2),
                "profit_estimate": round(float(row[6] or 0), 2),
                "logistics_cost": round(float((row[7] or 0) + (row[8] or 0)), 2),
                "storage_cost": round(float(row[9] or 0), 2),
            }
            for row in rows
        ],
    }


@router.get("/plan-status")
async def get_plan_status():
    today = date.today()
    month_start = today.replace(day=1)
    month_str = today.strftime("%Y-%m")

    async with async_session() as db:
        plan_r = await db.execute(text(
            "SELECT nm_id, plan_orders FROM product_plans WHERE month = :m"
        ), {"m": month_str})
        plans = {row[0]: row[1] for row in plan_r.fetchall()}

        if not plans:
            return {"month": month_str, "day": today.day, "items": [],
                    "total_plan": 0, "total_actual": 0, "overall_on_track": None}

        nm_ids = list(plans.keys())
        r = await db.execute(text("""
            SELECT p.nm_id, p.vendor_code, p.title, COALESCE(SUM(s.order_count), 0)
            FROM products p
            LEFT JOIN product_daily_stats s ON s.nm_id = p.nm_id AND s.date >= :start AND s.date <= :end
            WHERE p.nm_id = ANY(:nms)
            GROUP BY p.id
        """), {"start": month_start, "end": today, "nms": nm_ids})

        items = []
        total_plan = 0
        total_actual = 0
        for row in r.fetchall():
            plan = plans.get(row[0], 0)
            actual = row[3]
            total_plan += plan
            total_actual += actual
            expected = plan * today.day / 30
            items.append({
                "nm_id": row[0], "vendor_code": row[1], "title": row[2],
                "plan": plan, "actual": actual,
                "progress_pct": round(actual / plan * 100, 1) if plan > 0 else 0,
                "on_track": actual >= expected, "expected_today": round(expected),
            })

        return {
            "month": month_str, "day": today.day, "items": items,
            "total_plan": total_plan, "total_actual": total_actual,
            "overall_on_track": total_actual >= (total_plan * today.day / 30) if total_plan > 0 else None,
        }


# ===================== ADVERTISING ANALYTICS =====================

@router.get("/advertising-summary")
async def advertising_summary(
    days: int = Query(default=28, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Aggregated advertising metrics + orders + DRR for the period."""
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        # Ad metrics from product_daily_stats (fresher data)
        ad_r = await db.execute(text("""
            SELECT
                COALESCE(SUM(ad_views), 0)  AS views,
                COALESCE(SUM(ad_clicks), 0) AS clicks,
                COALESCE(SUM(ad_spend), 0)  AS spend,
                0 AS atc,
                COALESCE(SUM(ad_orders), 0) AS ad_orders
            FROM product_daily_stats
            WHERE date BETWEEN :s AND :e
        """), {"s": start, "e": end})
        ad = ad_r.fetchone()

        # Orders (all sources) from product_daily_stats
        ord_r = await db.execute(text("""
            SELECT
                COALESCE(SUM(order_count), 0) AS orders,
                COALESCE(SUM(order_sum), 0)   AS order_sum
            FROM product_daily_stats
            WHERE date BETWEEN :s AND :e
        """), {"s": start, "e": end})
        orders = ord_r.fetchone()

        # Revenue (buyouts) from realization_daily_stats
        rev_r = await db.execute(text("""
            SELECT COALESCE(SUM(sales_revenue), 0) AS revenue
            FROM realization_daily_stats
            WHERE stat_date BETWEEN :s AND :e
        """), {"s": start, "e": end})
        revenue = rev_r.scalar() or 0

    views = ad[0] or 0
    clicks = ad[1] or 0
    spend = float(ad[2] or 0)
    atc = ad[3] or 0
    ad_orders_cnt = ad[4] or 0
    total_orders = orders[0] or 0
    total_order_sum = float(orders[1] or 0)

    ctr = round(clicks / views * 100, 2) if views > 0 else 0
    cpm = round(spend / views * 1000, 2) if views > 0 else 0
    cpc = round(spend / clicks, 2) if clicks > 0 else 0
    cpo = round(spend / total_orders, 2) if total_orders > 0 else 0
    drr = round(spend / revenue * 100, 2) if revenue > 0 else 0

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "views": views,
        "clicks": clicks,
        "ctr": ctr,
        "cpm": cpm,
        "cpc": cpc,
        "spend": round(spend, 2),
        "add_to_cart": atc,
        "ad_orders": ad_orders_cnt,
        "total_orders": total_orders,
        "total_order_sum": round(total_order_sum, 2),
        "revenue": round(revenue, 2),
        "cpo": cpo,
        "drr": drr,
    }


@router.get("/advertising-products")
async def advertising_products(
    days: int = Query(default=28, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Per-product advertising metrics + total orders + CPO + DRR."""
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        # Ad metrics per product from product_daily_stats (fresher data)
        ad_r = await db.execute(text("""
            SELECT
                nm_id,
                COALESCE(SUM(ad_views), 0)  AS views,
                COALESCE(SUM(ad_clicks), 0) AS clicks,
                COALESCE(SUM(ad_spend), 0)  AS spend,
                0 AS atc,
                COALESCE(SUM(ad_orders), 0) AS ad_orders
            FROM product_daily_stats
            WHERE date BETWEEN :s AND :e
              AND ad_spend > 0
            GROUP BY nm_id
        """), {"s": start, "e": end})
        ad_rows = ad_r.fetchall()

        # Orders per product
        ord_r = await db.execute(text("""
            SELECT nm_id,
                COALESCE(SUM(order_count), 0) AS orders,
                COALESCE(SUM(order_sum), 0)   AS order_sum
            FROM product_daily_stats
            WHERE date BETWEEN :s AND :e
            GROUP BY nm_id
        """), {"s": start, "e": end})
        ord_rows = ord_r.fetchall()

        # Revenue per product
        rev_r = await db.execute(text("""
            SELECT nm_id, COALESCE(SUM(sales_revenue), 0) AS revenue
            FROM realization_daily_stats
            WHERE stat_date BETWEEN :s AND :e
            GROUP BY nm_id
        """), {"s": start, "e": end})
        rev_rows = rev_r.fetchall()

        # Product info
        prod_r = await db.execute(text(
            "SELECT nm_id, vendor_code, title, brand FROM products"
        ))
        prod_rows = prod_r.fetchall()

    ad_map = {}
    for row in ad_rows:
        ad_map[row[0]] = {
            "views": row[1], "clicks": row[2], "spend": float(row[3]),
            "atc": row[4], "ad_orders": row[5],
        }
    ord_map = {}
    for row in ord_rows:
        ord_map[row[0]] = {"orders": row[1], "order_sum": float(row[2])}
    rev_map = {row[0]: float(row[1]) for row in rev_rows}
    prod_map = {row[0]: {"vendor_code": row[1], "title": row[2], "brand": row[3]}
                for row in prod_rows}

    items = []
    for nm_id in sorted(ad_map.keys(), key=lambda x: ad_map[x]["spend"], reverse=True):
        ad = ad_map[nm_id]
        od = ord_map.get(nm_id, {"orders": 0, "order_sum": 0})
        revenue = rev_map.get(nm_id, 0)
        prod = prod_map.get(nm_id, {"vendor_code": "", "title": "", "brand": ""})
        views = ad["views"]
        clicks = ad["clicks"]
        spend = ad["spend"]
        total_orders = od["orders"]

        items.append({
            "nm_id": nm_id,
            "vendor_code": prod["vendor_code"],
            "title": prod["title"],
            "brand": prod["brand"],
            "views": views,
            "clicks": clicks,
            "ctr": round(clicks / views * 100, 2) if views > 0 else 0,
            "cpm": round(spend / views * 1000, 2) if views > 0 else 0,
            "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
            "spend": round(spend, 2),
            "atc": ad["atc"],
            "ad_orders": ad["ad_orders"],
            "total_orders": total_orders,
            "total_order_sum": round(od["order_sum"], 2),
            "revenue": round(revenue, 2),
            "cpo": round(spend / total_orders, 2) if total_orders > 0 else 0,
            "drr": round(spend / revenue * 100, 2) if revenue > 0 else 0,
        })

    return {"date_from": start.isoformat(), "date_to": end.isoformat(), "items": items}


@router.get("/advertising-daily")
async def advertising_daily(
    days: int = Query(default=28, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Daily advertising totals for charts."""
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(text("""
            SELECT
                date AS stat_date,
                COALESCE(SUM(ad_views), 0)  AS views,
                COALESCE(SUM(ad_clicks), 0) AS clicks,
                COALESCE(SUM(ad_spend), 0)  AS spend,
                COALESCE(SUM(ad_orders), 0) AS ad_orders
            FROM product_daily_stats
            WHERE date BETWEEN :s AND :e
              AND ad_spend > 0
            GROUP BY date
            ORDER BY date
        """), {"s": start, "e": end})
        rows = r.fetchall()

    items = []
    for row in rows:
        views = row[1]
        clicks = row[2]
        spend = float(row[3])
        items.append({
            "date": row[0].isoformat(),
            "views": views,
            "clicks": clicks,
            "spend": round(spend, 2),
            "ctr": round(clicks / views * 100, 2) if views > 0 else 0,
            "cpm": round(spend / views * 1000, 2) if views > 0 else 0,
            "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
            "ad_orders": row[4],
        })

    return {"date_from": start.isoformat(), "date_to": end.isoformat(), "items": items}


@router.get("/product-daily-stats/{nm_id}")
async def product_daily_stats(
    nm_id: int,
    days: int = Query(default=30, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Daily orders, buyouts, ad spend from product_daily_stats for a single product."""
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        r = await db.execute(text("""
            SELECT
                date,
                COALESCE(order_count, 0) AS order_count,
                COALESCE(order_sum, 0) AS order_sum,
                COALESCE(buyout_count, 0) AS buyout_count,
                COALESCE(buyout_sum, 0) AS buyout_sum,
                COALESCE(ad_views, 0) AS ad_views,
                COALESCE(ad_clicks, 0) AS ad_clicks,
                COALESCE(ad_spend, 0) AS ad_spend,
                COALESCE(ad_orders, 0) AS ad_orders,
                COALESCE(avg_price_before_spp, 0) AS avg_price
            FROM product_daily_stats
            WHERE nm_id = :nm AND date BETWEEN :s AND :e
            ORDER BY date
        """), {"nm": nm_id, "s": start, "e": end})
        rows = r.fetchall()

    items = []
    for row in rows:
        order_count = row[1]
        order_sum = float(row[2])
        avg_order_price = round(order_sum / order_count, 0) if order_count > 0 else 0
        items.append({
            "date": row[0].isoformat(),
            "order_count": order_count,
            "order_sum": round(order_sum, 2),
            "buyout_count": row[3],
            "buyout_sum": round(float(row[4]), 2),
            "ad_views": row[5],
            "ad_clicks": row[6],
            "ad_spend": round(float(row[7]), 2),
            "ad_orders": row[8],
            "avg_price": round(float(row[9]), 0),
            "avg_order_price": avg_order_price,
        })

    return {"nm_id": nm_id, "date_from": start.isoformat(), "date_to": end.isoformat(), "daily": items}


@router.get("/product-drawer/{nm_id}")
async def product_drawer(
    nm_id: int,
    days: int = Query(default=28, ge=1, le=3660),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Combined daily data for product drawer: orders from product_daily_stats, buyouts from realization_daily_stats."""
    start, end = _resolve_period(days, date_from, date_to)
    async with async_session() as db:
        # Orders + ad data from product_daily_stats
        ord_r = await db.execute(text("""
            SELECT date, order_count, order_sum, ad_spend, ad_views, ad_clicks, ad_orders
            FROM product_daily_stats
            WHERE nm_id = :nm AND date >= :s AND date <= :e
            ORDER BY date
        """), {"nm": nm_id, "s": start, "e": end})
        orders_by_date = {}
        for row in ord_r.fetchall():
            d = row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0])
            orders_by_date[d] = {
                "date": d,
                "order_count": row[1] or 0,
                "order_sum": float(row[2] or 0),
                "ad_spend": float(row[3] or 0),
                "ad_views": row[4] or 0,
                "ad_clicks": row[5] or 0,
                "ad_orders": row[6] or 0,
            }

        # Buyouts from realization_daily_stats
        buy_r = await db.execute(text("""
            SELECT stat_date, sales_count, sales_revenue
            FROM realization_daily_stats
            WHERE nm_id = :nm AND stat_date >= :s AND stat_date <= :e
            ORDER BY stat_date
        """), {"nm": nm_id, "s": start, "e": end})
        buyouts_by_date = {}
        for row in buy_r.fetchall():
            d = row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0])
            buyouts_by_date[d] = {"buyout_count": row[1] or 0, "buyout_revenue": float(row[2] or 0)}

        # Merge
        all_dates = sorted(set(list(orders_by_date.keys()) + list(buyouts_by_date.keys())))
        items = []
        for d in all_dates:
            o = orders_by_date.get(d, {"date": d, "order_count": 0, "order_sum": 0, "ad_spend": 0, "ad_views": 0, "ad_clicks": 0, "ad_orders": 0})
            b = buyouts_by_date.get(d, {"buyout_count": 0, "buyout_revenue": 0})
            oc = o["order_count"]
            asp = o["ad_spend"]
            item = {**o, **b}
            item["cpo"] = round(asp / oc, 2) if oc > 0 else 0
            items.append(item)

        total_orders = sum(i["order_count"] for i in items)
        total_buyouts = sum(i["buyout_count"] for i in items)
        total_ad_spend = sum(i["ad_spend"] for i in items)

        return {
            "nm_id": nm_id,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "daily": items,
            "totals": {
                "orders": total_orders,
                "buyouts": total_buyouts,
                "ad_spend": round(total_ad_spend, 2),
                "cpo": round(total_ad_spend / total_orders, 2) if total_orders > 0 else 0,
                "buyout_pct": round(total_buyouts / total_orders * 100, 1) if total_orders > 0 else 0,
            }
        }
