from fastapi import APIRouter, Query
from typing import Optional
from app.services.locator.locator_stocks import get_stock_summary, get_sales_funnel_summary
from app.services.locator.locator_calc import calc_article_dl, calc_irp_il

router = APIRouter(prefix="/api/locator", tags=["locator"])

@router.get("/summary")
async def locator_summary(force_refresh: bool = Query(False)):
    funnel = get_sales_funnel_summary(days=28, force_refresh=force_refresh)
    stocks = get_stock_summary(force_refresh=force_refresh)
    articles = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            articles.append(art)
    irp_il = calc_irp_il(articles)
    return {
        "il": irp_il["il"],
        "irp": irp_il["irp"],
        "totalOrders4w": irp_il["totalOrders"],
        "articles": articles,
        "updatedAt": None,
    }

@router.get("/dl")
async def locator_dl(force_refresh: bool = Query(False)):
    funnel = get_sales_funnel_summary(days=28, force_refresh=force_refresh)
    stocks = get_stock_summary(force_refresh=force_refresh)
    all_articles = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            all_articles.append(art)
    
    total_weighted_ktr = sum(a["ktr"] * a["orders_4w"] for a in all_articles)
    
    result = []
    for art in all_articles:
        vendor = art["vendorCode"]
        sizes_data = {}
        if vendor in stocks:
            for size, wh_data in stocks[vendor].items():
                total_qty = sum(info["quantity"] for info in wh_data.values())
                size_orders = round(art["orders_4w"] * total_qty / max(art["totalStock"], 1), 1) if art["totalStock"] > 0 else 0
                size_velocity = size_orders / 28
                size_days_to_oos = round(total_qty / max(size_velocity, 0.01), 1) if size_velocity > 0 else 999
                # Вычисляем влияние на ИЛ для размера
                size_il_weight = round(size_orders / max(art["orders_4w"], 1) * 100, 2) if art["orders_4w"] > 0 else 0
                sizes_data[size] = {
                    "dl": art["dl"],
                    "orders4w": size_orders,
                    "buyoutPercent": art["buyoutPercent"],
                    "stock": total_qty,
                    "daysToOOS": size_days_to_oos,
                    "ilWeight": size_il_weight,
                }
        
        il_weight = round(art["ktr"] * art["orders_4w"] / max(total_weighted_ktr, 1) * 100, 2) if total_weighted_ktr > 0 else 0
        result.append({
            "vendorCode": art["vendorCode"],
            "nmId": art["nmId"],
            "dl": art["dl"],
            "orders4w": art["orders_4w"],
            "buyoutPercent": art["buyoutPercent"],
            "totalStock": art["totalStock"],
            "daysToOOS": art["daysToOOS"],
            "ilWeight": il_weight,
            "sizes": sizes_data,
        })
    
    result.sort(key=lambda x: -x["ilWeight"])
    return {"articles": result}

@router.get("/alerts")
async def locator_alerts(force_refresh: bool = Query(False)):
    funnel = get_sales_funnel_summary(days=28, force_refresh=force_refresh)
    stocks = get_stock_summary(force_refresh=force_refresh)
    all_articles = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            all_articles.append(art)
    alerts = []
    for a in all_articles:
        for region, stock in a.get("stockByRegion", {}).items():
            if stock == 0 and a["orders_4w"] > 9:
                alerts.append({"type": "CRITICAL_ZERO", "severity": "HIGH", "message": f"{a['vendorCode']}: 0 остатков в {region} (заказов: {a['orders_4w']})"})
            if stock > 20 and a["dl"] < 60:
                alerts.append({"type": "OVERSTOCK", "severity": "MEDIUM", "message": f"{a['vendorCode']}: перетарка {stock} шт в {region}"})
        if a["is_breakthrough"]:
            alerts.append({"type": "BREAKTHROUGH_ZONE", "severity": "HIGH", "message": f"{a['vendorCode']}: ДЛ={a['dl']}% — зона пробития"})
        if a["daysToOOS"] < 7 and a["orders_4w"] > 0:
            alerts.append({"type": "OOS_SOON", "severity": "HIGH", "message": f"{a['vendorCode']}: OOS через {a['daysToOOS']:.1f} дн"})
    return {"alerts": alerts, "total": len(alerts)}
