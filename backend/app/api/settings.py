from datetime import datetime, date, timedelta
from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import async_session
from app.models.product import Product, ProductPlan
from app.models.settings import AppSettings
from app.services.logistics_calc import calc_metrics

router = APIRouter(prefix="/settings", tags=["settings"])


class GlobalSettings(BaseModel):
    ktr: Optional[float] = None
    irp: Optional[float] = None
    tax_rate: Optional[float] = None
    vat_rate: Optional[float] = None


class ProductCostInput(BaseModel):
    nm_id: int
    cost_price: float


class ProductPlanInput(BaseModel):
    nm_id: int
    month: str
    plan_orders: int


@router.get("/")
async def get_settings():
    async with async_session() as db:
        r = await db.execute(select(AppSettings))
        return {"settings": {s.key: s.value for s in r.scalars().all()}}


@router.put("/global")
async def update_global_settings(data: GlobalSettings):
    async with async_session() as db:
        now = datetime.now().isoformat()
        if data.ktr is not None:
            await _upsert_setting(db, "ktr", str(data.ktr))
            await _upsert_setting(db, "ktr_updated_at", now)
        if data.irp is not None:
            await _upsert_setting(db, "irp", str(data.irp))
            await _upsert_setting(db, "irp_updated_at", now)
        if data.tax_rate is not None:
            await _upsert_setting(db, "tax_rate", str(data.tax_rate))
        if data.vat_rate is not None:
            await _upsert_setting(db, "vat_rate", str(data.vat_rate))
        await db.commit()

    # Recalculate all metrics with new settings
    await _recalculate_all_metrics()
    return {"status": "ok", "recalculated": True}


@router.put("/cost-price")
async def update_cost_price(data: ProductCostInput):
    async with async_session() as db:
        r = await db.execute(select(Product).where(Product.nm_id == data.nm_id))
        product = r.scalar_one_or_none()
        if not product:
            return {"error": "Product not found"}
        product.cost_price = data.cost_price
        await db.commit()

    # Recalculate metrics for this product
    await _recalculate_product_metrics(data.nm_id)
    return {"status": "ok", "nm_id": data.nm_id, "cost_price": data.cost_price}


@router.put("/plan")
async def update_plan(data: ProductPlanInput):
    async with async_session() as db:
        stmt = pg_insert(ProductPlan).values(
            nm_id=data.nm_id, month=data.month, plan_orders=data.plan_orders,
        ).on_conflict_do_update(
            constraint="uq_product_plans_nm_month",
            set_={"plan_orders": data.plan_orders}
        )
        await db.execute(stmt)
        await db.commit()
    return {"status": "ok", "nm_id": data.nm_id, "month": data.month, "plan": data.plan_orders}


@router.get("/plans")
async def get_plans(month: str = None):
    if not month:
        month = date.today().strftime("%Y-%m")
    async with async_session() as db:
        r = await db.execute(
            select(ProductPlan).where(ProductPlan.month == month)
        )
        return {"month": month, "plans": [
            {"nm_id": p.nm_id, "plan_orders": p.plan_orders} for p in r.scalars().all()
        ]}


async def _upsert_setting(db, key: str, value: str):
    stmt = pg_insert(AppSettings).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
    await db.execute(stmt)


async def _get_all_settings(db) -> dict:
    r = await db.execute(select(AppSettings))
    return {s.key: s.value for s in r.scalars().all()}


async def _get_commission_map() -> dict:
    """Get commission rates by subject name."""
    from app.services.wb_api.client import wb_client
    from app.services.wb_api.token_loader import ensure_token
    try:
        await ensure_token()
        data = await wb_client.get_commissions()
        if data:
            result = {}
            for item in data:
                kgvp = item.get("kgvpMarketplace", 0)
                result[item.get("parentName", "")] = kgvp
                for sub in item.get("subjectList", []):
                    result[sub.get("subjectName", "")] = sub.get("kgvpMarketplace", kgvp)
            return result
    except:
        pass
    return {}


async def _recalculate_all_metrics():
    """Recalculate delivery/return/margin for ALL daily stats using products.buyout_percent."""
    async with async_session() as db:
        settings = await _get_all_settings(db)
        ktr = float(settings.get("ktr", "1.0"))
        irp = float(settings.get("irp", "0"))
        tax_rate = float(settings.get("tax_rate", "7"))
        vat_rate = float(settings.get("vat_rate", "0"))
        commission_default = float(settings.get("commission_rate", "35.5"))
        default_first_liter_rate = float(settings.get("first_liter_rate", "82.8"))
        default_extra_liter_rate = float(settings.get("extra_liter_rate", "25.2"))

        # Get commission map
        comm_map = await _get_commission_map()

        # Get stock quantities
        stock_r = await db.execute(text("SELECT nm_id, SUM(quantity) FROM stock_snapshots GROUP BY nm_id"))
        stock_map = {row[0]: row[1] for row in stock_r.fetchall()}

        # Join daily_stats with products to get buyout_percent, volume, cost etc
        r = await db.execute(text("""
            SELECT s.id, s.nm_id, s.order_count, s.order_sum,
                   s.buyout_count, s.buyout_sum, s.ad_spend,
                   p.cost_price, p.volume_liters, p.warehouse_coef,
                   p.subject_name, p.buyout_percent
            FROM product_daily_stats s
            JOIN products p ON p.nm_id = s.nm_id
        """))
        rows = r.fetchall()

        count = 0
        for row in rows:
            stat_id = row[0]
            nm_id = row[1]
            order_count = row[2] or 0
            order_sum = float(row[3] or 0)
            buyout_count = row[4] or 0
            buyout_sum = float(row[5] or 0)
            ad_spend_val = float(row[6] or 0)
            cost_price = float(row[7] or 0)
            volume_liters = float(row[8] or 0)
            warehouse_coef = float(row[9] or 1.0)
            subject_name = row[10] or ""
            buyout_pct = float(row[11] or 0)  # FROM products table!

            comm_pct = comm_map.get(subject_name, commission_default)
            if comm_pct <= 0:
                comm_pct = commission_default
            stock_qty = stock_map.get(nm_id, 0)

            metrics = calc_metrics(
                order_count=order_count,
                order_sum=order_sum,
                buyout_count=buyout_count,
                buyout_sum=buyout_sum,
                buyout_percent=buyout_pct,
                cost_price=cost_price,
                volume_liters=volume_liters,
                first_liter_rate=default_first_liter_rate,
                extra_liter_rate=default_extra_liter_rate,
                warehouse_coef=warehouse_coef,
                ktr=ktr,
                irp=irp,
                commission_pct=comm_pct,
                ad_spend=ad_spend_val,
                tax_rate=tax_rate,
                vat_rate=vat_rate,
                stock_quantity=stock_qty,
            )

            await db.execute(text("""
                UPDATE product_daily_stats SET
                    delivery_cost = :del, return_cost = :ret, storage_cost = :sto,
                    commission_amount = :comm, commission_pct = :comm_pct,
                    cost_price_total = :cost, margin_profit = :mp, margin_profit_pct = :mpp,
                    margin_clean = :mc, margin_clean_pct = :mcp, roi = :roi,
                    profit_per_order = :ppo
                WHERE id = :id
            """), {
                "del": metrics["delivery_cost"], "ret": metrics["return_cost"],
                "sto": metrics["storage_cost"], "comm": metrics["commission_amount"],
                "comm_pct": metrics["commission_pct"], "cost": metrics["cost_price_total"],
                "mp": metrics["margin_profit"], "mpp": metrics["margin_profit_pct"],
                "mc": metrics["margin_clean"], "mcp": metrics["margin_clean_pct"],
                "roi": metrics["roi"], "ppo": metrics["profit_per_order"], "id": stat_id,
            })
            count += 1

        await db.commit()
        print(f"Recalculated {count} records")



async def _recalculate_product_metrics(nm_id: int):
    """Recalculate metrics for a single product."""
    async with async_session() as db:
        settings = await _get_all_settings(db)
        ktr = float(settings.get("ktr", "1.0"))
        irp = float(settings.get("irp", "0"))
        tax_rate = float(settings.get("tax_rate", "7"))
        vat_rate = float(settings.get("vat_rate", "0"))
        commission_default = float(settings.get("commission_rate", "35.5"))
        default_first_liter_rate = float(settings.get("first_liter_rate", "82.8"))
        default_extra_liter_rate = float(settings.get("extra_liter_rate", "25.2"))

        # Get product info including buyout_percent
        pr = await db.execute(text("""
            SELECT cost_price, volume_liters, warehouse_coef, subject_name, buyout_percent
            FROM products WHERE nm_id = :nm
        """), {"nm": nm_id})
        prod = pr.fetchone()
        if not prod:
            return

        cost_price = float(prod[0] or 0)
        volume_liters = float(prod[1] or 0)
        warehouse_coef = float(prod[2] or 1.0)
        subject_name = prod[3] or ""
        buyout_pct = float(prod[4] or 0)

        comm_map = await _get_commission_map()
        comm_pct = comm_map.get(subject_name, commission_default)
        if comm_pct <= 0:
            comm_pct = commission_default

        stock_r = await db.execute(text(
            "SELECT COALESCE(SUM(quantity), 0) FROM stock_snapshots WHERE nm_id = :nm"
        ), {"nm": nm_id})
        stock_qty = stock_r.scalar() or 0

        r = await db.execute(text("""
            SELECT id, order_count, order_sum, buyout_count, buyout_sum, ad_spend
            FROM product_daily_stats WHERE nm_id = :nm
        """), {"nm": nm_id})

        for row in r.fetchall():
            metrics = calc_metrics(
                order_count=row[1] or 0,
                order_sum=float(row[2] or 0),
                buyout_count=row[3] or 0,
                buyout_sum=float(row[4] or 0),
                buyout_percent=buyout_pct,
                cost_price=cost_price,
                volume_liters=volume_liters,
                first_liter_rate=default_first_liter_rate,
                extra_liter_rate=default_extra_liter_rate,
                warehouse_coef=warehouse_coef,
                ktr=ktr, irp=irp,
                commission_pct=comm_pct,
                ad_spend=float(row[5] or 0),
                tax_rate=tax_rate, vat_rate=vat_rate,
                stock_quantity=stock_qty,
            )

            await db.execute(text("""
                UPDATE product_daily_stats SET
                    delivery_cost = :del, return_cost = :ret, storage_cost = :sto,
                    commission_amount = :comm, commission_pct = :comm_pct,
                    cost_price_total = :cost, margin_profit = :mp, margin_profit_pct = :mpp,
                    margin_clean = :mc, margin_clean_pct = :mcp, roi = :roi,
                    profit_per_order = :ppo
                WHERE id = :id
            """), {
                "del": metrics["delivery_cost"], "ret": metrics["return_cost"],
                "sto": metrics["storage_cost"], "comm": metrics["commission_amount"],
                "comm_pct": metrics["commission_pct"], "cost": metrics["cost_price_total"],
                "mp": metrics["margin_profit"], "mpp": metrics["margin_profit_pct"],
                "mc": metrics["margin_clean"], "mcp": metrics["margin_clean_pct"],
                "roi": metrics["roi"], "ppo": metrics["profit_per_order"], "id": row[0],
            })

        await db.commit()
