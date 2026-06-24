"""
Data synchronization service.
Pulls data from WB APIs, calculates metrics, stores in DB.
"""
import asyncio
import logging
import os
from datetime import date, timedelta, datetime
from typing import Optional

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.product import Product, ProductDailyStat, ProductPlan, StockSnapshot
from app.models.settings import AppSettings
from app.services.wb_api.client import wb_client
from app.services.wb_api.token_loader import ensure_token
from app.services.logistics_calc import calc_volume_liters, calc_metrics

logger = logging.getLogger(__name__)


async def _get_setting(db, key: str, default: str = "0") -> str:
    r = await db.execute(select(AppSettings).where(AppSettings.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


async def _get_all_settings(db) -> dict:
    r = await db.execute(select(AppSettings))
    return {s.key: s.value for s in r.scalars().all()}


async def _get_commission_map(db) -> dict:
    """Get commission rates by subject_id from WB API."""
    try:
        await ensure_token()
        data = await wb_client.get_commissions()
        if data:
            # Map parentName -> commission %
            result = {}
            for item in data:
                parent = item.get("parentName", "")
                kgvp_marketplace = item.get("kgvpMarketplace", 0)
                kgvp_supplier = item.get("kgvpSupplier", 0)
                kgvp_booking = item.get("kgvpBooking", 0)
                # Use marketplace commission as default
                result[parent] = kgvp_marketplace
                for sub in item.get("subjectList", []):
                    result[sub.get("subjectName", "")] = sub.get("kgvpMarketplace", kgvp_marketplace)
            return result
    except Exception as e:
        logger.error(f"Failed to get commissions: {e}")
    return {}


async def _get_weighted_tariffs(db) -> dict:
    """
    Calculate weighted average first_liter_rate and extra_liter_rate
    for each nm_id based on stock distribution across warehouses.
    Returns: {nm_id: (first_liter_rate, extra_liter_rate, warehouse_coef)}
    """
    # Get all stock snapshots with quantities
    r = await db.execute(text("""
        SELECT ss.nm_id, ss.warehouse_name, ss.quantity,
               wt.first_liter_rate, wt.extra_liter_rate
        FROM stock_snapshots ss
        LEFT JOIN warehouse_tariffs wt ON wt.warehouse_name = ss.warehouse_name
        WHERE ss.quantity > 0
    """))
    rows = r.fetchall()

    # Default tariff (average Russia)
    DEFAULT_FIRST = 73.6
    DEFAULT_EXTRA = 22.4
    DEFAULT_COEF = 1.6

    from collections import defaultdict
    nm_stocks = defaultdict(list)
    for nm_id, wh_name, qty, first, extra in rows:
        nm_stocks[nm_id].append((qty, first or DEFAULT_FIRST, extra or DEFAULT_EXTRA))

    result = {}
    for nm_id, stocks in nm_stocks.items():
        total_qty = sum(s[0] for s in stocks)
        if total_qty == 0:
            result[nm_id] = (DEFAULT_FIRST, DEFAULT_EXTRA, DEFAULT_COEF)
            continue
        weighted_first = sum(s[0] * s[1] for s in stocks) / total_qty
        weighted_extra = sum(s[0] * s[2] for s in stocks) / total_qty
        # warehouse_coef for storage: weighted_first / 46.0 (base tariff)
        weighted_coef = weighted_first / 46.0
        result[nm_id] = (weighted_first, weighted_extra, weighted_coef)

    return result


async def _ensure_realization_daily_table(db):
    await db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS realization_daily_stats (
                id SERIAL PRIMARY KEY,
                stat_date DATE NOT NULL,
                nm_id BIGINT NOT NULL DEFAULT 0,
                sales_count INTEGER NOT NULL DEFAULT 0,
                sales_revenue DOUBLE PRECISION NOT NULL DEFAULT 0,
                returns_count INTEGER NOT NULL DEFAULT 0,
                returns_revenue DOUBLE PRECISION NOT NULL DEFAULT 0,
                logistics_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                rebill_logistics_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                storage_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                acceptance_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                deduction_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                penalty_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
                additional_payment DOUBLE PRECISION NOT NULL DEFAULT 0,
                acquiring_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
                acquiring_returns DOUBLE PRECISION NOT NULL DEFAULT 0,
                commission_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
                commission_returns DOUBLE PRECISION NOT NULL DEFAULT 0,
                payout_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
                payout_returns DOUBLE PRECISION NOT NULL DEFAULT 0,
                net_payout DOUBLE PRECISION NOT NULL DEFAULT 0,
                net_qty INTEGER NOT NULL DEFAULT 0,
                cost_price_estimate DOUBLE PRECISION NOT NULL DEFAULT 0,
                profit_estimate DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT now(),
                UNIQUE(stat_date, nm_id)
            )
            """
        )
    )


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _pick_first_existing(data: dict, keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in data and data.get(key) not in ("", None):
            return _to_float(data.get(key), default)
    return default


async def _get_warehouse_tariffs() -> dict:
    """
    Get warehouse tariffs map:
      warehouse -> {"coef": float, "first_liter_rate": float, "extra_liter_rate": float}
    """
    try:
        await ensure_token()
        data = await wb_client.get_box_tariffs()
        wh_list = data.get("response", {}).get("data", {}).get("warehouseList", []) if data else []
        result = {}
        for wh in wh_list:
            name = wh.get("warehouseName", "")
            if not name:
                continue

            coef_raw = _pick_first_existing(
                wh,
                ["boxDeliveryCoefExpr", "deliveryCoefExpr", "boxStorageCoefExpr"],
                100.0,
            )
            coef = coef_raw / 100.0 if coef_raw > 3 else coef_raw
            if coef <= 0:
                coef = 1.0

            first_liter_rate = _pick_first_existing(
                wh,
                [
                    "boxDeliveryBase",
                    "deliveryBase",
                    "firstLitre",
                    "firstLiter",
                    "boxDeliveryFirstLitre",
                    "boxDeliveryFirstLiter",
                ],
                0.0,
            )
            extra_liter_rate = _pick_first_existing(
                wh,
                [
                    "boxDeliveryLiter",
                    "deliveryLiter",
                    "extraLitre",
                    "extraLiter",
                    "boxDeliveryExtraLitre",
                    "boxDeliveryExtraLiter",
                ],
                0.0,
            )

            result[name] = {
                "coef": coef,
                "first_liter_rate": first_liter_rate,
                "extra_liter_rate": extra_liter_rate,
            }
        return result
    except Exception as e:
        logger.error(f"Failed to get warehouse tariffs: {e}")
    return {}


def _weighted_tariffs_for_nm(
    nm_id: int,
    stock_warehouse_map: dict,
    warehouse_tariffs: dict,
    default_first_liter_rate: float,
    default_extra_liter_rate: float,
) -> tuple[float, float]:
    """
    Weighted by stock quantity across warehouses.
    stock_warehouse_map[nm_id] -> list[(warehouse_name, quantity)]
    """
    rows = stock_warehouse_map.get(nm_id, [])
    if not rows:
        return default_first_liter_rate, default_extra_liter_rate

    total_qty = sum(max(int(qty or 0), 0) for _, qty in rows)
    if total_qty <= 0:
        return default_first_liter_rate, default_extra_liter_rate

    first_acc = 0.0
    extra_acc = 0.0
    for wh_name, qty in rows:
        qty = max(int(qty or 0), 0)
        if qty == 0:
            continue
        t = warehouse_tariffs.get(wh_name, {})
        first_rate = _to_float(t.get("first_liter_rate"), default_first_liter_rate)
        extra_rate = _to_float(t.get("extra_liter_rate"), default_extra_liter_rate)
        w = qty / total_qty
        first_acc += first_rate * w
        extra_acc += extra_rate * w

    if first_acc <= 0:
        first_acc = default_first_liter_rate
    if extra_acc <= 0:
        extra_acc = default_extra_liter_rate

    return first_acc, extra_acc


async def sync_products_and_dimensions():
    """Sync product cards with dimensions from Content API."""
    logger.info("Syncing products and dimensions...")
    await ensure_token()

    try:
        cards = await wb_client.get_all_cards()
    except Exception as e:
        logger.error(f"Failed to fetch cards: {e}")
        return

    if not cards:
        logger.warning("No cards returned")
        return

    # Get warehouse tariffs for coefficients
    try:
        tariff_map = await _get_warehouse_tariffs()
    except Exception:
        tariff_map = {}

    # Get stock info for warehouse mapping
    try:
        stocks = await wb_client.get_stocks()
    except Exception:
        stocks = []

    # Build nm_id -> warehouse map from stocks
    nm_warehouse = {}
    for s in (stocks or []):
        nm = s.get("nmId")
        wh = s.get("warehouseName", "")
        if nm and wh:
            nm_warehouse[nm] = wh

    async with async_session() as db:
        count = 0
        for card in cards:
            nm_id = card.get("nmID")
            if not nm_id:
                continue

            dims = card.get("dimensions", {})
            w = float(dims.get("width", 0))
            h = float(dims.get("height", 0))
            l = float(dims.get("length", 0))
            weight = float(dims.get("weightBrutto", 0))
            vol = calc_volume_liters(w, h, l)

            wh_name = nm_warehouse.get(nm_id, "")
            wh_coef = tariff_map.get(wh_name, {}).get("coef", 1.0)

            stmt = pg_insert(Product).values(
                nm_id=nm_id,
                vendor_code=card.get("vendorCode", ""),
                title=card.get("title", ""),
                brand=card.get("brand", ""),
                subject_id=card.get("subjectID", 0),
                subject_name=card.get("subjectName", ""),
                width_cm=w,
                height_cm=h,
                length_cm=l,
                weight_kg=weight,
                volume_liters=round(vol, 3),
                warehouse_name=wh_name,
                warehouse_coef=wh_coef,
            ).on_conflict_do_update(
                index_elements=["nm_id"],
                set_={
                    "vendor_code": card.get("vendorCode", ""),
                    "title": card.get("title", ""),
                    "brand": card.get("brand", ""),
                    "subject_id": card.get("subjectID", 0),
                    "subject_name": card.get("subjectName", ""),
                    "width_cm": w,
                    "height_cm": h,
                    "length_cm": l,
                    "weight_kg": weight,
                    "volume_liters": round(vol, 3),
                    "warehouse_name": wh_name,
                    "warehouse_coef": wh_coef,
                }
            )
            await db.execute(stmt)
            count += 1

        await db.commit()
        logger.info(f"Synced {count} products with dimensions")
        print(f"  Synced {count} products with dimensions")


async def sync_daily_stats(days: int = 7, date_from: date | None = None, date_to: date | None = None):
    """Sync sales funnel history and calculate metrics."""
    logger.info(f"Syncing daily stats for {days} days...")
    await ensure_token()

    end = date_to or date.today()
    start = date_from or (end - timedelta(days=days))
    if start > end:
        start, end = end, start

    async with async_session() as db:
        # Get all product nm_ids
        r = await db.execute(select(Product.nm_id))
        all_nms = [row[0] for row in r.fetchall()]

        if not all_nms:
            logger.warning("No products in DB")
            return

        # Get settings
        settings = await _get_all_settings(db)
        ktr = float(settings.get("ktr", "1.0"))
        irp = float(settings.get("irp", "0"))
        tax_rate = float(settings.get("tax_rate", "7"))
        vat_rate = float(settings.get("vat_rate", "0"))

        # Get commission map
        comm_map = await _get_commission_map(db)

        # Get products info
        r = await db.execute(select(Product))
        products = {p.nm_id: p for p in r.scalars().all()}

        # Get stock quantities
        r = await db.execute(
            text("SELECT nm_id, SUM(quantity) FROM stock_snapshots GROUP BY nm_id")
        )
        stock_map = {row[0]: row[1] for row in r.fetchall()}

    # Fetch history from API in batches and date windows (WB limit can be strict, use 7 days)
    batch_size = 20
    all_history = []

    current_start = start
    window_idx = 1
    while current_start <= end:
        current_end = min(current_start + timedelta(days=6), end)
        print(f"  History window {window_idx}: {current_start}..{current_end}")
        for i in range(0, len(all_nms), batch_size):
            batch = all_nms[i:i + batch_size]
            try:
                data = await wb_client.get_sales_history(
                    nm_ids=batch,
                    start=current_start.isoformat(),
                    end=current_end.isoformat()
                )
                if data:
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("data", [])
                        if isinstance(items, list) and items and isinstance(items[0], dict) and "product" not in items[0]:
                            items = data.get("data", {}).get("cards", data.get("data", []))
                    else:
                        items = []
                    all_history.extend(items)
                    print(f"  History batch {i // batch_size + 1}: {len(items)} items")
            except Exception as e:
                logger.error(f"History batch error: {e}")

            if i + batch_size < len(all_nms):
                await asyncio.sleep(25)
        current_start = current_end + timedelta(days=1)
        window_idx += 1

    # Process history into daily stats
    async with async_session() as db:
        settings = await _get_all_settings(db)
        ktr = float(settings.get("ktr", "1.0"))
        irp = float(settings.get("irp", "0"))
        tax_rate = float(settings.get("tax_rate", "7"))
        vat_rate = float(settings.get("vat_rate", "0"))
        commission_default = float(settings.get("commission_rate", "3.5"))
        default_first_liter_rate = float(settings.get("first_liter_rate", "82.8"))
        default_extra_liter_rate = float(settings.get("extra_liter_rate", "25.2"))

        r = await db.execute(select(Product))
        products = {p.nm_id: p for p in r.scalars().all()}
        comm_map_local = await _get_commission_map(db)
        warehouse_tariffs = await _get_warehouse_tariffs()

        stock_r = await db.execute(
            text("SELECT nm_id, SUM(quantity) FROM stock_snapshots GROUP BY nm_id")
        )
        stock_map_local = {row[0]: row[1] for row in stock_r.fetchall()}
        stock_wh_r = await db.execute(
            text(
                """
                SELECT nm_id, warehouse_name, SUM(quantity) AS qty
                FROM stock_snapshots
                GROUP BY nm_id, warehouse_name
                """
            )
        )
        stock_warehouse_map = {}
        for nm, wh, qty in stock_wh_r.fetchall():
            stock_warehouse_map.setdefault(nm, []).append((wh, qty))

        count = 0
        debug_counter = 0
        for item in all_history:
            product_info = item.get("product", {})
            nm_id = product_info.get("nmId") or item.get("nmID")
            if not nm_id:
                continue

            history = item.get("history", [])
            if debug_counter < 5:
                print(f"  Item {nm_id}: history len {len(history)}")
                debug_counter += 1

            for day_data in history:
                dt_str = day_data.get("date", day_data.get("dt", ""))[:10]
                try:
                    dt = date.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    continue

                opens = day_data.get("openCount", 0)
                carts = day_data.get("cartCount", 0)
                orders = day_data.get("orderCount", 0)
                order_sum = day_data.get("orderSum", 0)
                buyouts = day_data.get("buyoutCount", 0)
                buyout_sum = day_data.get("buyoutSum", 0)
                buyout_pct = day_data.get("buyoutPercent", 0)
                cancels = day_data.get("cancelCount", 0)
                cancel_sum = day_data.get("cancelSum", 0)

                # Calculate metrics if product exists
                product = products.get(nm_id)
                metrics = {}
                if product and orders > 0:
                    comm_pct = comm_map_local.get(product.subject_name, commission_default)
                    if comm_pct <= 0:
                        comm_pct = commission_default
                    stock_qty = stock_map_local.get(nm_id, 0)
                    first_liter_rate, extra_liter_rate = _weighted_tariffs_for_nm(
                        nm_id=nm_id,
                        stock_warehouse_map=stock_warehouse_map,
                        warehouse_tariffs=warehouse_tariffs,
                        default_first_liter_rate=default_first_liter_rate,
                        default_extra_liter_rate=default_extra_liter_rate,
                    )
                    # Use product-level buyout % for logistics calc (daily bp is unreliable)
                    effective_bp = product.buyout_percent or buyout_pct or 20
                    if effective_bp < 5:
                        effective_bp = 20  # fallback for too low values
                    metrics = calc_metrics(
                        order_count=orders,
                        order_sum=order_sum,
                        buyout_count=buyouts,
                        buyout_sum=buyout_sum,
                        buyout_percent=effective_bp,
                        returns_count=0,  # not available at order time
                        cost_price=product.cost_price or 0,
                        volume_liters=product.volume_liters or 0,
                        first_liter_rate=first_liter_rate,
                        extra_liter_rate=extra_liter_rate,
                        warehouse_coef=product.warehouse_coef or 1.0,
                        ktr=ktr,
                        irp=irp,
                        commission_pct=comm_pct,
                        seller_coef=0.647,
                        acquiring_pct=2.6,
                        logistics_multiplier=1.85,
                        ad_spend=0,  # will be updated by ad sync
                        tax_rate=tax_rate,
                        vat_rate=vat_rate,
                        stock_quantity=stock_qty,
                    )

                # Calculate net order_sum (gross minus WB commission)
                net_comm_pct = comm_map_local.get(product.subject_name, commission_default) if product else commission_default
                net_order_sum = round(order_sum * (1 - net_comm_pct / 100), 2) if net_comm_pct > 0 else order_sum

                upsert_sql = text("""
                    INSERT INTO product_daily_stats (
                        nm_id, date, open_count, cart_count,
                        order_count, order_sum, buyout_count, buyout_sum, buyout_percent,
                        cancel_count, cancel_sum,
                        delivery_cost, return_cost, storage_cost,
                        commission_amount, commission_pct,
                        cost_price_total, margin_profit, margin_profit_pct,
                        margin_clean, margin_clean_pct, roi, profit_per_order
                    ) VALUES (
                        :nm_id, :dt, :open_count, :cart_count,
                        :order_count, :order_sum, :buyout_count, :buyout_sum, :buyout_percent,
                        :cancel_count, :cancel_sum,
                        :delivery_cost, :return_cost, :storage_cost,
                        :commission_amount, :commission_pct,
                        :cost_price_total, :margin_profit, :margin_profit_pct,
                        :margin_clean, :margin_clean_pct, :roi, :profit_per_order
                    )
                    ON CONFLICT (nm_id, date) DO UPDATE SET
                        open_count = CASE WHEN EXCLUDED.open_count > 0 THEN EXCLUDED.open_count ELSE product_daily_stats.open_count END,
                        cart_count = CASE WHEN EXCLUDED.cart_count > 0 THEN EXCLUDED.cart_count ELSE product_daily_stats.cart_count END,
                        order_count = CASE WHEN EXCLUDED.order_count > 0 THEN EXCLUDED.order_count ELSE product_daily_stats.order_count END,
                        order_sum = CASE WHEN product_daily_stats.order_sum > 0 THEN product_daily_stats.order_sum ELSE EXCLUDED.order_sum END,
                        buyout_count = CASE WHEN EXCLUDED.buyout_count > 0 THEN EXCLUDED.buyout_count ELSE product_daily_stats.buyout_count END,
                        buyout_sum = CASE WHEN EXCLUDED.buyout_sum > 0 THEN EXCLUDED.buyout_sum ELSE product_daily_stats.buyout_sum END,
                        buyout_percent = CASE WHEN EXCLUDED.buyout_percent > 0 THEN EXCLUDED.buyout_percent ELSE product_daily_stats.buyout_percent END,
                        cancel_count = CASE WHEN EXCLUDED.cancel_count > 0 THEN EXCLUDED.cancel_count ELSE product_daily_stats.cancel_count END,
                        cancel_sum = CASE WHEN EXCLUDED.cancel_sum > 0 THEN EXCLUDED.cancel_sum ELSE product_daily_stats.cancel_sum END,
                        delivery_cost = CASE WHEN EXCLUDED.delivery_cost > 0 THEN EXCLUDED.delivery_cost ELSE product_daily_stats.delivery_cost END,
                        return_cost = CASE WHEN EXCLUDED.return_cost > 0 THEN EXCLUDED.return_cost ELSE product_daily_stats.return_cost END,
                        storage_cost = CASE WHEN EXCLUDED.storage_cost > 0 THEN EXCLUDED.storage_cost ELSE product_daily_stats.storage_cost END,
                        commission_amount = CASE WHEN EXCLUDED.commission_amount > 0 THEN EXCLUDED.commission_amount ELSE product_daily_stats.commission_amount END,
                        commission_pct = CASE WHEN EXCLUDED.commission_pct > 0 THEN EXCLUDED.commission_pct ELSE product_daily_stats.commission_pct END,
                        cost_price_total = CASE WHEN EXCLUDED.cost_price_total > 0 THEN EXCLUDED.cost_price_total ELSE product_daily_stats.cost_price_total END,
                        margin_profit = CASE WHEN EXCLUDED.margin_profit > 0 THEN EXCLUDED.margin_profit ELSE product_daily_stats.margin_profit END,
                        margin_profit_pct = CASE WHEN EXCLUDED.margin_profit_pct > 0 THEN EXCLUDED.margin_profit_pct ELSE product_daily_stats.margin_profit_pct END,
                        margin_clean = CASE WHEN EXCLUDED.margin_clean > 0 THEN EXCLUDED.margin_clean ELSE product_daily_stats.margin_clean END,
                        margin_clean_pct = CASE WHEN EXCLUDED.margin_clean_pct > 0 THEN EXCLUDED.margin_clean_pct ELSE product_daily_stats.margin_clean_pct END,
                        roi = CASE WHEN EXCLUDED.roi > 0 THEN EXCLUDED.roi ELSE product_daily_stats.roi END,
                        profit_per_order = CASE WHEN EXCLUDED.profit_per_order > 0 THEN EXCLUDED.profit_per_order ELSE product_daily_stats.profit_per_order END
                """)
                await db.execute(upsert_sql, {
                    "nm_id": nm_id, "dt": dt,
                    "open_count": opens, "cart_count": carts,
                    "order_count": orders, "order_sum": net_order_sum,
                    "buyout_count": buyouts, "buyout_sum": buyout_sum, "buyout_percent": buyout_pct,
                    "cancel_count": cancels, "cancel_sum": cancel_sum,
                    "delivery_cost": metrics.get("delivery_cost", 0),
                    "return_cost": metrics.get("return_cost", 0),
                    "storage_cost": metrics.get("storage_cost", 0),
                    "commission_amount": metrics.get("commission_amount", 0),
                    "commission_pct": metrics.get("commission_pct", 0),
                    "cost_price_total": metrics.get("cost_price_total", 0),
                    "margin_profit": metrics.get("margin_profit", 0),
                    "margin_profit_pct": metrics.get("margin_profit_pct", 0),
                    "margin_clean": metrics.get("margin_clean", 0),
                    "margin_clean_pct": metrics.get("margin_clean_pct", 0),
                    "roi": metrics.get("roi", 0),
                    "profit_per_order": metrics.get("profit_per_order", 0),
                })
                count += 1

        await db.commit()
        logger.info(f"Synced {count} daily stat records")
        print(f"  Synced {count} daily stat records with metrics")


async def sync_ad_stats(days: int = 7, date_from: date | None = None, date_to: date | None = None):
    """Sync advertising stats and merge into daily stats."""
    logger.info("Syncing ad stats...")
    await ensure_token()

    # Get active campaigns
    try:
        promo = await wb_client.get_promotion_campaigns()
    except Exception as e:
        logger.error(f"Failed to get campaigns: {e}")
        return

    if not promo:
        return

    # Extract active campaign IDs (status 9 = active)
    active_ids = []
    for group in promo.get("adverts", promo if isinstance(promo, list) else []):
        if group.get("status") == 9:
            for adv in group.get("advert_list", []):
                active_ids.append(adv.get("advertId"))

    if not active_ids:
        logger.info("No active campaigns")
        return

    print(f"  Active campaigns: {active_ids}")

    end = date_to or date.today()
    start = date_from or (end - timedelta(days=days))
    if start > end:
        start, end = end, start

    # Collect ad data per nm_id+date
    ad_data = {}  # (nm_id, date_str) -> {views, clicks, spend, atbs, orders}

    for cid in active_ids:
        try:
            await asyncio.sleep(62)  # Rate limit
            data = await wb_client.get_fullstats(
                campaign_id=cid,
                date_from=start.isoformat(),
                date_to=end.isoformat()
            )
            if not data:
                continue

            for adv in (data if isinstance(data, list) else [data]):
                for day in adv.get("days", []):
                    dt_str = day.get("date", "")[:10]
                    for app in day.get("apps", []):
                        for nm in app.get("nms", app.get("nm", [])):
                            nm_id = nm.get("nmId", 0)
                            key = (nm_id, dt_str)
                            if key not in ad_data:
                                ad_data[key] = {"views": 0, "clicks": 0, "spend": 0, "atbs": 0, "orders": 0}
                            ad_data[key]["views"] += nm.get("views", 0)
                            ad_data[key]["clicks"] += nm.get("clicks", 0)
                            ad_data[key]["spend"] += nm.get("sum", 0)
                            ad_data[key]["atbs"] += nm.get("atbs", 0)
                            ad_data[key]["orders"] += nm.get("orders", 0)

            print(f"  Campaign {cid}: fetched ad data")
        except Exception as e:
            logger.error(f"Fullstats error for {cid}: {e}")

    if not ad_data:
        print("  No ad data collected")
        return

    # Update daily stats with ad data
    async with async_session() as db:
        settings = await _get_all_settings(db)
        ktr = float(settings.get("ktr", "1.0"))
        irp = float(settings.get("irp", "0"))
        tax_rate = float(settings.get("tax_rate", "7"))
        vat_rate = float(settings.get("vat_rate", "0"))
        commission_default = float(settings.get("commission_rate", "3.5"))
        default_first_liter_rate = float(settings.get("first_liter_rate", "82.8"))
        default_extra_liter_rate = float(settings.get("extra_liter_rate", "25.2"))

        r = await db.execute(select(Product))
        products = {p.nm_id: p for p in r.scalars().all()}
        comm_map_local = await _get_commission_map(db)
        warehouse_tariffs = await _get_warehouse_tariffs()
        stock_r = await db.execute(
            text("SELECT nm_id, SUM(quantity) FROM stock_snapshots GROUP BY nm_id")
        )
        stock_map_local = {row[0]: row[1] for row in stock_r.fetchall()}
        stock_wh_r = await db.execute(
            text(
                """
                SELECT nm_id, warehouse_name, SUM(quantity) AS qty
                FROM stock_snapshots
                GROUP BY nm_id, warehouse_name
                """
            )
        )
        stock_warehouse_map = {}
        for nm, wh, qty in stock_wh_r.fetchall():
            stock_warehouse_map.setdefault(nm, []).append((wh, qty))

        count = 0
        for (nm_id, dt_str), ad in ad_data.items():
            try:
                dt = date.fromisoformat(dt_str)
            except (ValueError, TypeError):
                continue

            views = ad["views"]
            clicks = ad["clicks"]
            spend = ad["spend"]
            ctr = (clicks / views * 100) if views > 0 else 0
            cpc = (spend / clicks) if clicks > 0 else 0

            # Get existing stat to recalculate margin
            r = await db.execute(
                select(ProductDailyStat).where(
                    ProductDailyStat.nm_id == nm_id,
                    ProductDailyStat.date == dt
                )
            )
            existing = r.scalar_one_or_none()

            new_margin_clean = 0
            new_roi = 0
            if existing and existing.order_count > 0:
                product = products.get(nm_id)
                if product:
                    comm_pct = comm_map_local.get(product.subject_name, commission_default)
                    if comm_pct <= 0:
                        comm_pct = commission_default
                    stock_qty = stock_map_local.get(nm_id, 0)
                    first_liter_rate, extra_liter_rate = _weighted_tariffs_for_nm(
                        nm_id=nm_id,
                        stock_warehouse_map=stock_warehouse_map,
                        warehouse_tariffs=warehouse_tariffs,
                        default_first_liter_rate=default_first_liter_rate,
                        default_extra_liter_rate=default_extra_liter_rate,
                    )
                    metrics = calc_metrics(
                        order_count=existing.order_count,
                        order_sum=existing.order_sum,
                        buyout_count=existing.buyout_count,
                        buyout_sum=existing.buyout_sum,
                        buyout_percent=product.buyout_percent or existing.buyout_percent or 20,
                        returns_count=0,  # not available at order time
                        cost_price=product.cost_price or 0,
                        volume_liters=product.volume_liters or 0,
                        first_liter_rate=first_liter_rate,
                        extra_liter_rate=extra_liter_rate,
                        warehouse_coef=product.warehouse_coef or 1.0,
                        ktr=ktr,
                        irp=irp,
                        commission_pct=comm_pct,
                        seller_coef=0.647,
                        acquiring_pct=2.6,
                        logistics_multiplier=1.85,
                        ad_spend=spend,
                        tax_rate=tax_rate,
                        vat_rate=vat_rate,
                        stock_quantity=stock_qty,
                    )
                    new_margin_clean = metrics.get("margin_clean", 0)
                    new_roi = metrics.get("roi", 0)

            await db.execute(
                text("""
                    UPDATE product_daily_stats
                    SET ad_views = :v, ad_clicks = :c, ad_ctr = :ctr,
                        ad_cpc = :cpc, ad_spend = :s, ad_atbs = :a, ad_orders = :o,
                        margin_clean = :mc, roi = :roi
                    WHERE nm_id = :nm AND date = :dt
                """),
                {
                    "v": views, "c": clicks, "ctr": round(ctr, 2),
                    "cpc": round(cpc, 2), "s": round(spend, 2),
                    "a": ad["atbs"], "o": ad["orders"],
                    "mc": round(new_margin_clean, 2), "roi": round(new_roi, 2),
                    "nm": nm_id, "dt": dt
                }
            )
            count += 1

        await db.commit()
        print(f"  Updated {count} daily stats with ad data")


async def sync_stocks():
    """Sync stock snapshots."""
    logger.info("Syncing stocks...")
    await ensure_token()
    try:
        stocks = await wb_client.get_stocks()
    except Exception as e:
        logger.error(f"Failed to get stocks: {e}")
        return

    if not stocks:
        return

    async with async_session() as db:
        # Clear old snapshots
        await db.execute(text("DELETE FROM stock_snapshots"))

        count = 0
        for s in stocks:
            nm_id = s.get("nmId")
            if not nm_id:
                continue
            stmt = pg_insert(StockSnapshot).values(
                nm_id=nm_id,
                warehouse_name=s.get("warehouseName", ""),
                quantity=s.get("quantity", 0),
                in_way_to_client=s.get("inWayToClient", 0),
                sizes_count=1,
            )
            await db.execute(stmt)
            count += 1

        await db.commit()
        print(f"  Synced {count} stock records")


async def sync_realization_daily(date_from: date, date_to: date):
    """Fetch realization report and persist daily financial history."""
    logger.info(f"Syncing realization daily stats: {date_from}..{date_to}")
    await ensure_token()

    data = await wb_client.get_realization_report(date_from.isoformat(), date_to.isoformat())
    if not data:
        print("  No realization data")
        return

    async with async_session() as db:
        await _ensure_realization_daily_table(db)

        r = await db.execute(select(Product.nm_id, Product.cost_price))
        cost_map = {row[0]: float(row[1] or 0) for row in r.fetchall()}

        agg = {}
        for row in data:
            rr_dt = row.get("rr_dt")
            if not rr_dt:
                continue
            stat_date = date.fromisoformat(rr_dt[:10])
            nm_id = int(row.get("nm_id") or 0)
            key = (stat_date, nm_id)
            item = agg.setdefault(
                key,
                {
                    "sales_count": 0,
                    "sales_revenue": 0.0,
                    "returns_count": 0,
                    "returns_revenue": 0.0,
                    "logistics_cost": 0.0,
                    "rebill_logistics_cost": 0.0,
                    "storage_cost": 0.0,
                    "acceptance_cost": 0.0,
                    "deduction_cost": 0.0,
                    "penalty_cost": 0.0,
                    "additional_payment": 0.0,
                    "acquiring_sales": 0.0,
                    "acquiring_returns": 0.0,
                    "commission_sales": 0.0,
                    "commission_returns": 0.0,
                    "payout_sales": 0.0,
                    "payout_returns": 0.0,
                },
            )

            op = row.get("supplier_oper_name", "") or ""
            qty = int(row.get("quantity") or 0)
            retail_amount = _to_float(row.get("retail_amount"), 0.0)
            retail_with_disc = _to_float(row.get("retail_price_withdisc_rub"), 0.0)
            delivery_rub = _to_float(row.get("delivery_rub"), 0.0)
            rebill_logistic_cost = _to_float(row.get("rebill_logistic_cost"), 0.0)
            storage_fee = _to_float(row.get("storage_fee"), 0.0)
            acceptance = _to_float(row.get("acceptance"), 0.0)
            deduction = _to_float(row.get("deduction"), 0.0)
            penalty = _to_float(row.get("penalty"), 0.0)
            additional_payment = _to_float(row.get("additional_payment"), 0.0)
            acquiring_fee = _to_float(row.get("acquiring_fee"), 0.0)
            commission = abs(_to_float(row.get("ppvz_sales_commission"), 0.0))
            payout = _to_float(row.get("ppvz_for_pay"), 0.0)

            if op == "Продажа":
                item["sales_count"] += qty or 1
                item["sales_revenue"] += retail_amount
                item["acquiring_sales"] += acquiring_fee
                item["commission_sales"] += commission
                item["payout_sales"] += payout
            elif op == "Возврат":
                item["returns_count"] += qty or 1
                item["returns_revenue"] += retail_amount
                item["acquiring_returns"] += acquiring_fee
                item["commission_returns"] += commission
                item["payout_returns"] += payout
            elif op == "Логистика":
                item["logistics_cost"] += delivery_rub
            elif op == "Хранение":
                item["storage_cost"] += storage_fee
            elif op == "Возмещение за выдачу и возврат товаров на ПВЗ":
                item["logistics_cost"] += delivery_rub

            item["rebill_logistics_cost"] += rebill_logistic_cost
            item["acceptance_cost"] += acceptance
            item["deduction_cost"] += deduction
            item["penalty_cost"] += penalty
            item["additional_payment"] += additional_payment

        await db.execute(
            text(
                "DELETE FROM realization_daily_stats WHERE stat_date >= :start AND stat_date <= :end"
            ),
            {"start": date_from, "end": date_to},
        )

        upsert_sql = text(
            """
            INSERT INTO realization_daily_stats (
                stat_date, nm_id, sales_count, sales_revenue, returns_count, returns_revenue,
                logistics_cost, rebill_logistics_cost, storage_cost, acceptance_cost,
                deduction_cost, penalty_cost, additional_payment, acquiring_sales,
                acquiring_returns, commission_sales, commission_returns, payout_sales,
                payout_returns, net_payout, net_qty, cost_price_estimate, profit_estimate, updated_at
            ) VALUES (
                :stat_date, :nm_id, :sales_count, :sales_revenue, :returns_count, :returns_revenue,
                :logistics_cost, :rebill_logistics_cost, :storage_cost, :acceptance_cost,
                :deduction_cost, :penalty_cost, :additional_payment, :acquiring_sales,
                :acquiring_returns, :commission_sales, :commission_returns, :payout_sales,
                :payout_returns, :net_payout, :net_qty, :cost_price_estimate, :profit_estimate, now()
            )
            ON CONFLICT (stat_date, nm_id) DO UPDATE SET
                sales_count = EXCLUDED.sales_count,
                sales_revenue = EXCLUDED.sales_revenue,
                returns_count = EXCLUDED.returns_count,
                returns_revenue = EXCLUDED.returns_revenue,
                logistics_cost = EXCLUDED.logistics_cost,
                rebill_logistics_cost = EXCLUDED.rebill_logistics_cost,
                storage_cost = EXCLUDED.storage_cost,
                acceptance_cost = EXCLUDED.acceptance_cost,
                deduction_cost = EXCLUDED.deduction_cost,
                penalty_cost = EXCLUDED.penalty_cost,
                additional_payment = EXCLUDED.additional_payment,
                acquiring_sales = EXCLUDED.acquiring_sales,
                acquiring_returns = EXCLUDED.acquiring_returns,
                commission_sales = EXCLUDED.commission_sales,
                commission_returns = EXCLUDED.commission_returns,
                payout_sales = EXCLUDED.payout_sales,
                payout_returns = EXCLUDED.payout_returns,
                net_payout = EXCLUDED.net_payout,
                net_qty = EXCLUDED.net_qty,
                cost_price_estimate = EXCLUDED.cost_price_estimate,
                profit_estimate = EXCLUDED.profit_estimate,
                updated_at = now()
            """
        )

        count = 0
        for (stat_date, nm_id), item in agg.items():
            net_qty = item["sales_count"] - item["returns_count"]
            cost_price_estimate = cost_map.get(nm_id, 0.0) * net_qty
            net_payout = (
                item["payout_sales"]
                - item["payout_returns"]
                - item["logistics_cost"]
                - item["storage_cost"]
                - item["acceptance_cost"]
                - item["deduction_cost"]
                - item["penalty_cost"]
                + item["additional_payment"]
            )
            profit_estimate = net_payout - cost_price_estimate
            params = {
                "stat_date": stat_date,
                "nm_id": nm_id,
                **item,
                "net_payout": net_payout,
                "net_qty": net_qty,
                "cost_price_estimate": cost_price_estimate,
                "profit_estimate": profit_estimate,
            }
            await db.execute(upsert_sql, params)
            count += 1

        await db.commit()
        print(f"  Synced {count} realization daily records")



async def sync_buyout_percent():
    """Fetch 28-day buyout % from Sales Funnel API v3 and update products table."""
    from datetime import date, timedelta

    token = wb_client.token
    if not token:
        print("No token for buyout sync")
        return

    end = date.today()
    start = end - timedelta(days=28)

    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"
    headers = {"Authorization": token, "Content-Type": "application/json"}

    proxy = os.getenv("SOCKS5_PROXY", "")

    all_products = []
    page = 1

    async with httpx.AsyncClient(headers=headers, proxy=proxy or None, timeout=60) as client:
        while True:
            body = {
                "selectedPeriod": {
                    "start": start.strftime("%Y-%m-%d"),
                    "end": end.strftime("%Y-%m-%d")
                },
                "page": page,
                "limit": 100
            }
            try:
                resp = await client.post(url, json=body)
                if resp.status_code != 200:
                    print(f"Buyout API error page {page}: {resp.status_code} {resp.text[:200]}")
                    break
                data = resp.json()
                products = []
                if "data" in data:
                    d = data["data"]
                    if isinstance(d, dict):
                        products = d.get("products", [])
                    elif isinstance(d, list):
                        products = d
                if not products:
                    break
                all_products.extend(products)
                print(f"Buyout page {page}: {len(products)} products")
                if len(products) < 100:
                    break
                page += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Buyout fetch error page {page}: {e}")
                break

    print(f"Total buyout records: {len(all_products)}")

    updated = 0
    async with async_session() as db:
        for p in all_products:
            prod = p.get("product", {})
            nm_id = prod.get("nmId")
            if not nm_id:
                continue

            stat = p.get("statistic", {})
            sel = stat.get("selected", {})
            conv = sel.get("conversions", {})
            buyout_pct = conv.get("buyoutPercent", 0)
            order_count_28d = sel.get("orderCount", 0)
            buyout_count_28d = sel.get("buyoutCount", 0)
            cancel_count_28d = sel.get("cancelCount", 0)
            avg_price = sel.get("avgPrice", 0)

            try:
                await db.execute(
                    text("""
                        UPDATE products SET
                            buyout_percent = :bp,
                            avg_price_api = :ap
                        WHERE nm_id = :nm
                    """),
                    {"bp": buyout_pct, "ap": avg_price, "nm": nm_id}
                )
                updated += 1
            except Exception as e:
                print(f"Update error nm={nm_id}: {e}")

        await db.commit()
    print(f"Updated buyout % for {updated} products")


async def full_sync(days: int = 7, date_from: date | None = None, date_to: date | None = None):
    """Run full data synchronization."""
    print("Starting full sync...")

    print("Step 1: Products & dimensions...")
    await sync_products_and_dimensions()
    await asyncio.sleep(5)

    print("Step 2: Stocks...")
    await sync_stocks()
    await asyncio.sleep(5)

    print("Step 3: Daily stats & metrics...")
    await sync_daily_stats(days=days, date_from=date_from, date_to=date_to)

    print("Step 4: Ad stats (this takes ~5 min due to rate limits)...")
    await sync_ad_stats(days=days, date_from=date_from, date_to=date_to)

    print("Full sync complete!")
