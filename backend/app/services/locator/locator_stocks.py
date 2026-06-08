"""
Сервис получения данных из WB API через SOCKS5-прокси.
Остатки, заказы, продажи, воронка продаж (ДЛ, выкупаемость).
"""
import httpx
import os
from typing import Optional
from datetime import datetime, timedelta
from app.services.locator.locator_config import (
    SOCKS5_PROXY, WB_API_TOKEN, TRACKED_ARTICLES,
    WAREHOUSE_TO_REGION
)

STATISTICS_URL = "https://statistics-api.wildberries.ru"
ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"


def _client() -> httpx.Client:
    """Создаёт httpx клиент с SOCKS5 прокси."""
    return httpx.Client(
        proxy=SOCKS5_PROXY,
        timeout=60,
        verify=False,
        headers={"Authorization": WB_API_TOKEN}
    )


def get_stocks(date_from: str = None) -> list[dict]:
    """
    Возвращает остатки на складах WB.
    GET /api/v1/supplier/stocks
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    with _client() as c:
        r = c.get(f"{STATISTICS_URL}/api/v1/supplier/stocks",
                  params={"dateFrom": date_from})
        r.raise_for_status()
        return r.json()


def get_sales(date_from: str = None) -> list[dict]:
    """
    Возвращает продажи за период.
    GET /api/v1/supplier/sales?dateFrom=...
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")

    all_sales = []
    current_from = date_from

    with _client() as c:
        while True:
            r = c.get(f"{STATISTICS_URL}/api/v1/supplier/sales",
                      params={"dateFrom": current_from})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            all_sales.extend(batch)
            # Пагинация: берём lastChangeDate последней строки
            current_from = batch[-1]["lastChangeDate"]
            if len(batch) < 80000:  # не полный лимит — значит всё
                break

    return all_sales


def get_orders(date_from: str = None) -> list[dict]:
    """
    Возвращает заказы за период.
    GET /api/v1/supplier/orders?dateFrom=...
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")

    all_orders = []
    current_from = date_from

    with _client() as c:
        while True:
            r = c.get(f"{STATISTICS_URL}/api/v1/supplier/orders",
                      params={"dateFrom": current_from})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            all_orders.extend(batch)
            current_from = batch[-1]["lastChangeDate"]
            if len(batch) < 80000:
                break

    return all_orders


def get_sales_funnel(nm_ids: list[int], days: int = 28) -> list[dict]:
    """
    Воронка продаж v3: ДЛ, выкупаемость, заказы по каждому nmId.
    POST /api/analytics/v3/sales-funnel/products
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    body = {
        "nmIDs": nm_ids,
        "selectedPeriod": {"start": start_date, "end": end_date}
    }

    with _client() as c:
        r = c.post(
            f"{ANALYTICS_URL}/api/analytics/v3/sales-funnel/products",
            headers={"Authorization": WB_API_TOKEN, "Content-Type": "application/json"},
            json=body
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("products", [])


def get_filtered_stocks() -> list[dict]:
    """
    Остатки только по отслеживаемым артикулам.
    Возвращает [{barcode, supplierArticle, nmId, techSize, quantity,
                  warehouseName, brand, subject, ...}, ...]
    """
    all_stocks = get_stocks()
    return [s for s in all_stocks if s.get("supplierArticle") in TRACKED_ARTICLES]


def get_stock_summary() -> dict:
    """
    Сводка остатков: { "ТРЕНД22WHITE": { "42": {"Коледино": 5, ...}, ... }, ... }
    """
    stocks = get_filtered_stocks()
    summary = {}

    for s in stocks:
        art = s["supplierArticle"]
        size = s["techSize"]
        wh = s["warehouseName"]
        qty = s.get("quantity", 0)
        region = WAREHOUSE_TO_REGION.get(wh.lower(), "Прочее")

        if art not in summary:
            summary[art] = {}
        if size not in summary[art]:
            summary[art][size] = {}
        summary[art][size][wh] = {
            "quantity": qty,
            "quantityFull": s.get("quantityFull", qty),
            "inWayToClient": s.get("inWayToClient", 0),
            "inWayFromClient": s.get("inWayFromClient", 0),
            "region": region,
            "nmId": s["nmId"],
            "barcode": s["barcode"],
            "brand": s["brand"],
            "subject": s["subject"],
        }

    return summary


def get_sales_funnel_summary(days: int = 28) -> list[dict]:
    """
    Сводка воронки продаж для отслеживаемых артикулов.
    Возвращает [{vendorCode, nmId, dl, orders, buyouts,
                  buyoutPercent, avgOrdersPerDay, stockWb, ...}, ...]
    """
    stocks = get_filtered_stocks()
    tracked_nm_ids = list(set(s["nmId"] for s in stocks))

    funnel = get_sales_funnel(tracked_nm_ids, days)
    result = []

    for p in funnel:
        prod = p.get("product", {})
        stat = p.get("statistic", {}).get("selected", {})

        result.append({
            "vendorCode": prod.get("vendorCode"),
            "nmId": prod.get("nmId"),
            "brandName": prod.get("brandName"),
            "subjectName": prod.get("subjectName"),
            "dl": stat.get("localizationPercent", 0),
            "orders": stat.get("orderCount", 0),
            "buyouts": stat.get("buyoutCount", 0),
            "cancelCount": stat.get("cancelCount", 0),
            "orderSum": stat.get("orderSum", 0),
            "buyoutSum": stat.get("buyoutSum", 0),
            "avgOrdersPerDay": stat.get("avgOrdersCountPerDay", 0),
            "buyoutPercent": stat.get("conversions", {}).get("buyoutPercent", 0),
            "cartToOrderPercent": stat.get("conversions", {}).get("cartToOrderPercent", 0),
            "addToCartPercent": stat.get("conversions", {}).get("addToCartPercent", 0),
            "stockWb": prod.get("stocks", {}).get("wb", 0),
        })

    return result
