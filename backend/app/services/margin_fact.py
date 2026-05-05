# =================== НАЧАЛО ФАЙЛА margin_fact.py ===================
"""
Расчёт ФАКТИЧЕСКОЙ маржи по кассовому методу.

Источник данных: realization_daily_stats (агрегат отчёта реализации WB).
Эта таблица уже заполняется через sync_realization_daily из data_sync.py
и содержит все нужные поля, разложенные по дням и nm_id.

Формула маржи (по кассовому методу, по дате stat_date):
  margin = net_payout − cogs − ad_spend

Где:
  - net_payout         — готовое поле, "К перечислению с учётом всех удержаний WB"
                         (продажи минус возвраты минус логистика минус хранение
                          минус Корректировка ВВ минус штрафы минус приёмка)
  - cogs               — cost_price_estimate (готовое поле,
                         (sales_count − returns_count) × cost_price товара)
  - ad_spend           — из product_daily_stats.ad_spend (наша рекламная сторона)

Преимущество: данные сходятся с финотчётом WB до копейки по всем статьям.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _f(v) -> float:
    """Безопасное преобразование Decimal/None в float."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


async def calc_margin_for_day(
    db: AsyncSession,
    target_date: date,
    nm_id: Optional[int] = None,
) -> list[dict]:
    """
    Возвращает список словарей с маржой за день — по одному элементу на nm_id.
    Если nm_id указан, фильтрует только по нему.
    Если nm_id=None — все товары + строка nm_id=0 (общие расходы WB).

    ИЗМЕНЕНИЕ: добавлен LEFT JOIN products для получения vendor_code и title,
    чтобы в таблице SKU на фронте показывались артикул продавца и название.
    """
    sql = """
        SELECT
            rds.stat_date           AS date,
            rds.nm_id,
            COALESCE(p.vendor_code, '') AS vendor_code,
            COALESCE(p.title, '')       AS title,
            rds.sales_count,
            rds.sales_revenue,
            rds.returns_count,
            rds.returns_revenue,
            rds.payout_sales,
            rds.payout_returns,
            rds.logistics_cost,
            rds.rebill_logistics_cost,
            rds.storage_cost,
            rds.acceptance_cost,
            rds.deduction_cost,
            rds.penalty_cost,
            rds.additional_payment,
            rds.acquiring_sales,
            rds.acquiring_returns,
            rds.commission_sales,
            rds.commission_returns,
            rds.net_payout,
            rds.net_qty,
            rds.cost_price_estimate AS cogs,
            COALESCE(pds.ad_spend, 0) AS ad_spend
        FROM realization_daily_stats rds
        LEFT JOIN product_daily_stats pds
               ON pds.nm_id = rds.nm_id
              AND pds.date  = rds.stat_date
        LEFT JOIN products p
               ON p.nm_id   = rds.nm_id
        WHERE rds.stat_date = CAST(:target_date AS DATE)
          AND (CAST(:nm_id AS BIGINT) IS NULL OR rds.nm_id = CAST(:nm_id AS BIGINT))
        ORDER BY rds.nm_id
    """
    rows = (await db.execute(
        text(sql),
        {"target_date": target_date, "nm_id": nm_id},
    )).mappings().all()

    if not rows:
        logger.info(f"Нет записей в realization_daily_stats за {target_date}")
        return []

    result = []
    for r in rows:
        net_payout = _f(r["net_payout"])
        cogs       = _f(r["cogs"])
        ad_spend   = _f(r["ad_spend"])

        # Главная формула: маржа = net_payout − COGS − реклама
        # net_payout уже включает в себя все удержания WB (логистика, корр.ВВ и т.д.)
        margin = net_payout - cogs - ad_spend

        # Маржа в % от выручки (sales_revenue)
        revenue = _f(r["sales_revenue"])
        margin_pct = (margin / revenue * 100) if revenue > 0 else 0.0

        result.append({
            "date":            r["date"],
            "nm_id":           r["nm_id"],
            # НОВЫЕ поля: артикул продавца и название (для таблицы)
            "vendor_code":     r["vendor_code"] or "",
            "title":           r["title"] or "",
            # Объёмы
            "sales_count":     int(r["sales_count"] or 0),
            "returns_count":   int(r["returns_count"] or 0),
            "net_qty":         int(r["net_qty"] or 0),
            # Денежный поток
            "sales_revenue":   round(_f(r["sales_revenue"]),     2),
            "returns_revenue": round(_f(r["returns_revenue"]),   2),
            "payout_sales":    round(_f(r["payout_sales"]),      2),
            "payout_returns": round(_f(r["payout_returns"]),    2),
            # Удержания WB
            "logistics":       round(_f(r["logistics_cost"]) + _f(r["rebill_logistics_cost"]), 2),
            "storage":         round(_f(r["storage_cost"]),      2),
            "acceptance":      round(_f(r["acceptance_cost"]),   2),
            "deduction":       round(_f(r["deduction_cost"]),    2),  # Корректировка ВВ
            "penalty":         round(_f(r["penalty_cost"]),      2),
            "commission":      round(_f(r["commission_sales"]) - _f(r["commission_returns"]), 2),
            "acquiring":       round(_f(r["acquiring_sales"]) + _f(r["acquiring_returns"]), 2),
            # Себестоимость и реклама
            "cogs":            round(cogs,     2),
            "ad_spend":        round(ad_spend, 2),
            # Итог
            "net_payout":      round(net_payout, 2),
            "margin":          round(margin,    2),
            "margin_pct":      round(margin_pct, 2),
        })

    return result


async def calc_margin_for_period(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    nm_id: Optional[int] = None,
) -> list[dict]:
    """Маржа по дням за период [date_from, date_to] включительно."""
    out = []
    cur = date_from
    while cur <= date_to:
        rows = await calc_margin_for_day(db, cur, nm_id)
        out.extend(rows)
        cur += timedelta(days=1)
    return out


async def calc_margin_summary(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    nm_id: Optional[int] = None,
) -> dict:
    """
    Агрегированный итог за период — для KPI-карточек на дашборде.
    Возвращает один словарь со суммами по всем дням и товарам.
    """
    sql = """
        SELECT
            COUNT(DISTINCT rds.stat_date)                    AS days,
            SUM(rds.sales_count)                             AS sales_count,
            SUM(rds.returns_count)                           AS returns_count,
            SUM(rds.net_qty)                                 AS net_qty,
            SUM(rds.sales_revenue)                           AS sales_revenue,
            SUM(rds.returns_revenue)                         AS returns_revenue,
            SUM(rds.payout_sales - rds.payout_returns)       AS to_pay,
            SUM(rds.logistics_cost + rds.rebill_logistics_cost) AS logistics,
            SUM(rds.storage_cost)                            AS storage,
            SUM(rds.deduction_cost)                          AS deduction,
            SUM(rds.penalty_cost)                            AS penalty,
            SUM(rds.acceptance_cost)                         AS acceptance,
            SUM(rds.commission_sales - rds.commission_returns) AS commission,
            SUM(rds.acquiring_sales + rds.acquiring_returns) AS acquiring,
            SUM(rds.cost_price_estimate)                     AS cogs,
            SUM(rds.net_payout)                              AS net_payout,
            COALESCE((
                SELECT SUM(pds.ad_spend)
                FROM product_daily_stats pds
                WHERE pds.date BETWEEN CAST(:dfrom AS DATE) AND CAST(:dto AS DATE)
                  AND (CAST(:nm_id AS BIGINT) IS NULL OR pds.nm_id = CAST(:nm_id AS BIGINT))
            ), 0)                                            AS ad_spend
        FROM realization_daily_stats rds
        WHERE rds.stat_date BETWEEN CAST(:dfrom AS DATE) AND CAST(:dto AS DATE)
          AND (CAST(:nm_id AS BIGINT) IS NULL OR rds.nm_id = CAST(:nm_id AS BIGINT))
    """
    r = (await db.execute(
        text(sql),
        {"dfrom": date_from, "dto": date_to, "nm_id": nm_id},
    )).mappings().one()

    net_payout = _f(r["net_payout"])
    cogs       = _f(r["cogs"])
    ad_spend   = _f(r["ad_spend"])
    margin     = net_payout - cogs - ad_spend
    revenue    = _f(r["sales_revenue"])

    return {
        "date_from":        date_from,
        "date_to":          date_to,
        "days":             int(r["days"] or 0),
        "sales_count":      int(r["sales_count"] or 0),
        "returns_count":    int(r["returns_count"] or 0),
        "net_qty":          int(r["net_qty"] or 0),
        "sales_revenue":    round(revenue, 2),
        "returns_revenue":  round(_f(r["returns_revenue"]), 2),
        "to_pay":           round(_f(r["to_pay"]),     2),
        "logistics":        round(_f(r["logistics"]),  2),
        "storage":          round(_f(r["storage"]),    2),
        "deduction":        round(_f(r["deduction"]),  2),
        "penalty":          round(_f(r["penalty"]),    2),
        "acceptance":       round(_f(r["acceptance"]), 2),
        "commission":       round(_f(r["commission"]), 2),
        "acquiring":        round(_f(r["acquiring"]),  2),
        "cogs":             round(cogs,                2),
        "ad_spend":         round(ad_spend,            2),
        "net_payout":       round(net_payout,          2),
        "margin":           round(margin,              2),
        "margin_pct":       round((margin / revenue * 100) if revenue > 0 else 0, 2),
    }
# =================== КОНЕЦ ФАЙЛА margin_fact.py ===================
