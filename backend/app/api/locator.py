"""
API-роутер модуля Locator.
Эндпоинты: /api/locator/*
"""
from fastapi import APIRouter, Query
from typing import Optional

from app.services.locator.locator_stocks import (
    get_filtered_stocks, get_stock_summary,
    get_sales_funnel_summary, get_stocks
)
from app.services.locator.locator_calc import (
    calc_article_dl, calc_irp_il, recommend_shipments
)
from app.services.locator.locator_packing import (
    generate_packing_list, format_packing_table
)

router = APIRouter(prefix="/api/locator", tags=["locator"])


@router.get("/summary")
async def locator_summary():
    """
    Сводка: ИЛ, ИРП, ДЛ по артикулам, дни до OOS.
    """
    # Воронка продаж (ДЛ, выкупаемость, заказы)
    funnel = get_sales_funnel_summary(days=28)

    # Остатки по складам
    stocks = get_stock_summary()

    # Расчёт по каждому артикулу
    articles = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            articles.append(art)

    # Общий ИРП/ИЛ
    irp_il = calc_irp_il(articles)

    return {
        "il": irp_il["il"],
        "irp": irp_il["irp"],
        "totalOrders4w": irp_il["totalOrders"],
        "articles": articles,
        "updatedAt": None,  # TODO: добавить timestamp
    }


@router.get("/stocks")
async def locator_stocks(
    article: Optional[str] = Query(None, description="Фильтр по артикулу"),
    warehouse: Optional[str] = Query(None, description="Фильтр по складу"),
):
    """Остатки WB: фильтр по артикулу и складу."""
    all_stocks = get_filtered_stocks()

    if article:
        all_stocks = [s for s in all_stocks if s.get("supplierArticle") == article]

    # Группировка по складам
    result = {}
    for s in all_stocks:
        art = s["supplierArticle"]
        wh = s["warehouseName"]
        if warehouse and wh.lower() != warehouse.lower():
            continue

        if art not in result:
            result[art] = []

        result[art].append({
            "size": s["techSize"],
            "warehouse": wh,
            "quantity": s.get("quantity", 0),
            "quantityFull": s.get("quantityFull", 0),
            "inWayToClient": s.get("inWayToClient", 0),
            "barcode": s["barcode"],
            "nmId": s["nmId"],
        })

    return {"stocks": result, "totalArticles": len(result)}


@router.get("/dl")
async def locator_dl():
    """ДЛ по артикулам с КТР/КРП."""
    funnel = get_sales_funnel_summary(days=28)
    stocks = get_stock_summary()

    result = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            result.append({
                "vendorCode": art["vendorCode"],
                "nmId": art["nmId"],
                "dl": art["dl"],
                "ktr": art["ktr"],
                "krp": art["krp"],
                "color": art["color"],
                "priority": art["priority"],
                "isBreakthrough": art["is_breakthrough"],
                "orders4w": art["orders_4w"],
                "buyouts4w": art["buyouts_4w"],
                "buyoutPercent": art["buyoutPercent"],
                "avgOrdersPerDay": art["avgOrdersPerDay"],
                "totalStock": art["totalStock"],
                "daysToOOS": art["daysToOOS"],
                "hasCriticalZeros": art["hasCriticalZeros"],
            })

    # Сортируем: сначала критические, потом зона пробития, потом остальные
    result.sort(key=lambda x: (
        not x["hasCriticalZeros"],
        not x["isBreakthrough"],
        x["dl"]
    ))

    return {"articles": result}


@router.get("/irp-history")
async def locator_irp_history():
    """История ИРП/ИЛ (пока только текущее значение — нужно накопить)."""
    funnel = get_sales_funnel_summary(days=28)
    stocks = get_stock_summary()
    articles = [calc_article_dl(stocks[f["vendorCode"]], f)
                for f in funnel if f.get("vendorCode") and f["vendorCode"] in stocks]
    irp_il = calc_irp_il(articles)

    return {
        "current": {"il": irp_il["il"], "irp": irp_il["irp"]},
        "history": [],  # TODO: сохранять в БД
    }


@router.get("/quick-wins")
async def locator_quick_wins():
    """Приоритетные SKU: ДЛ в зоне 50-59% с наибольшим объёмом заказов."""
    funnel = get_sales_funnel_summary(days=28)
    stocks = get_stock_summary()

    candidates = []
    for f in funnel:
        vendor = f.get("vendorCode")
        if vendor and vendor in stocks:
            art = calc_article_dl(stocks[vendor], f)
            if art["is_breakthrough"] or art["priority"] == "HIGH":
                # Эффект на ИРП: (КРП_сейчас - КРП_после) × Заказы / Общие_заказы
                from app.services.locator.locator_config import get_ktr_krp
                current_krp = art["krp"]
                future_krp = get_ktr_krp(60)[1]  # КРП при ДЛ=60% = 0
                # Вычисляем эффект на ИРП: (текущий_КРП - будущий_КРП) * заказы / общие_заказы
                all_orders_sum = max(1, sum([a["orders_4w"] for a in all_articles]))
                irp_effect = round((current_krp - future_krp) * art["orders_4w"] / all_orders_sum, 2)
                candidates.append({
                    "irpEffect": irp_effect,
                    "color": art["color"],
                })

    candidates.sort(key=lambda x: -x["irpEffect"])
    return {"quickWins": candidates[:10]}


@router.get("/recommendations")
async def locator_recommendations():
    """Рекомендации по поставкам."""
    funnel = get_sales_funnel_summary(days=28)
    stocks = get_stock_summary()

    articles = [calc_article_dl(stocks[f["vendorCode"]], f)
                for f in funnel if f.get("vendorCode") and f["vendorCode"] in stocks]

    recommendations = recommend_shipments(articles, stocks, {})
    return {"recommendations": recommendations, "totalBoxes": sum(r["boxesSuggested"] for r in recommendations)}


@router.get("/packing")
async def locator_packing(
    generate: bool = Query(False, description="Сгенерировать новый план?"),
):
    """План упаковки: коробки, состав."""
    if generate:
        funnel = get_sales_funnel_summary(days=28)
        stocks = get_stock_summary()
        articles = [calc_article_dl(stocks[f["vendorCode"]], f)
                    for f in funnel if f.get("vendorCode") and f["vendorCode"] in stocks]
        recommendations = recommend_shipments(articles, stocks, {}, max_boxes=10)
        boxes = generate_packing_list(recommendations, stocks)
        table = format_packing_table(boxes)
        return {"boxes": boxes, "table": table, "totalBoxes": len(boxes)}

    return {"boxes": [], "table": [], "message": "Передайте ?generate=true"}


@router.get("/alerts")
async def locator_alerts():
    """Активные алёрты: критические нули, перетарка, зона пробития."""
    funnel = get_sales_funnel_summary(days=28)
    stocks = get_stock_summary()
    articles = [calc_article_dl(stocks[f["vendorCode"]], f)
                for f in funnel if f.get("vendorCode") and f["vendorCode"] in stocks]

    alerts = []

    for a in articles:
        # Критические нули
        for region, stock in a.get("stockByRegion", {}).items():
            if stock == 0 and a["orders_4w"] > 9:
                alerts.append({
                    "type": "CRITICAL_ZERO",
                    "severity": "HIGH",
                    "message": f"{a['vendorCode']}: 0 остатков в {region} (заказов: {a['orders_4w']})",
                    "vendorCode": a["vendorCode"],
                    "region": region,
                })

        # Перетарка
        for region, stock in a.get("stockByRegion", {}).items():
            if stock > 20 and a["dl"] < 60:
                alerts.append({
                    "type": "OVERSTOCK",
                    "severity": "MEDIUM",
                    "message": f"{a['vendorCode']}: перетарка {stock} шт в {region}",
                    "vendorCode": a["vendorCode"],
                    "region": region,
                    "stock": stock,
                })

        # Зона пробития (ДЛ вошёл в 55-59%)
        if a["is_breakthrough"]:
            alerts.append({
                "type": "BREAKTHROUGH_ZONE",
                "severity": "HIGH",
                "message": f"{a['vendorCode']}: ДЛ={a['dl']}% — зона пробития (заказов: {a['orders_4w']})",
                "vendorCode": a["vendorCode"],
                "dl": a["dl"],
            })

        # Падение ДЛ ниже 60%
        if a["dl"] < 60 and a.get("pastDl", 100) >= 60:
            alerts.append({
                "type": "DL_DROP",
                "severity": "HIGH",
                "message": f"{a['vendorCode']}: ДЛ упал с {a.get('pastDl')}% до {a['dl']}%",
            })

        # OOS < 7 дней
        if a["daysToOOS"] < 7 and a["orders_4w"] > 0:
            alerts.append({
                "type": "OOS_SOON",
                "severity": "HIGH",
                "message": f"{a['vendorCode']}: OOS через {a['daysToOOS']:.1f} дн (сток: {a['totalStock']})",
                "vendorCode": a["vendorCode"],
                "daysToOOS": a["daysToOOS"],
            })

    return {"alerts": alerts, "total": len(alerts)}
