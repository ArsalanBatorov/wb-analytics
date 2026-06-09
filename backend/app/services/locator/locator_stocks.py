import httpx
import os
from datetime import datetime, timedelta
from typing import Optional
from app.services.locator.locator_config import SOCKS5_PROXY, WB_API_TOKEN, TRACKED_ARTICLES, WAREHOUSE_TO_REGION
from app.services.locator.locator_cache import get_cached_response, set_cached_response, init_cache

init_cache()

STATISTICS_URL = "https://statistics-api.wildberries.ru"
ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"

def _client() -> httpx.Client:
    return httpx.Client(proxy=SOCKS5_PROXY, timeout=60, verify=False, headers={"Authorization": WB_API_TOKEN})

def get_stocks(date_from: str = None, force_refresh: bool = False) -> list[dict]:
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    key = f"stocks_{date_from}"
    if not force_refresh:
        cached = get_cached_response(key)
        if cached is not None:
            return cached
    with _client() as c:
        r = c.get(f"{STATISTICS_URL}/api/v1/supplier/stocks", params={"dateFrom": date_from})
        r.raise_for_status()
        data = r.json()
    set_cached_response(key, data)
    return data

def get_sales_funnel(nm_ids: list[int], days: int = 28, force_refresh: bool = False) -> list[dict]:
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    key = f"funnel_{start_date}_{end_date}_{'_'.join(map(str, sorted(nm_ids)))}"
    if not force_refresh:
        cached = get_cached_response(key)
        if cached is not None:
            return cached
    body = {"nmIDs": nm_ids, "selectedPeriod": {"start": start_date, "end": end_date}}
    with _client() as c:
        r = c.post(f"{ANALYTICS_URL}/api/analytics/v3/sales-funnel/products",
                   headers={"Authorization": WB_API_TOKEN, "Content-Type": "application/json"},
                   json=body)
        r.raise_for_status()
        data = r.json().get("data", {}).get("products", [])
    set_cached_response(key, data)
    return data

# Остальные функции (get_filtered_stocks, get_stock_summary, get_sales_funnel_summary) остаются без изменений,
# но они вызывают get_stocks и get_sales_funnel, которые уже используют кэш.
# Для совместимости передадим force_refresh=False по умолчанию.
# При необходимости добавим параметр force_refresh в эти функции.

def get_filtered_stocks(force_refresh: bool = False) -> list[dict]:
    all_stocks = get_stocks(force_refresh=force_refresh)
    return [s for s in all_stocks if s.get("supplierArticle") in TRACKED_ARTICLES]

def get_stock_summary(force_refresh: bool = False) -> dict:
    stocks = get_filtered_stocks(force_refresh=force_refresh)
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

def get_sales_funnel_summary(days: int = 28, force_refresh: bool = False) -> list[dict]:
    stocks = get_filtered_stocks(force_refresh=force_refresh)
    tracked_nm_ids = list(set(s["nmId"] for s in stocks))
    funnel = get_sales_funnel(tracked_nm_ids, days, force_refresh=force_refresh)
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
