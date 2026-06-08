"""
Расчёт ДЛ, ИРП, ИЛ, дней до OOS, рекомендаций поставок.
"""
from app.services.locator.locator_config import (
    get_ktr_krp, is_breakthrough_zone, get_dl_color,
    REGIONS, WAREHOUSE_TO_REGION, SHIPMENT_PRIORITY,
    SAFETY_COEFFICIENT, ITEMS_PER_BOX, TROUSERS_PER_BOX,
    JUNE_SEASONALITY,
)


def calc_article_dl(article_stock_summary: dict, article_funnel: dict) -> dict:
    """
    Рассчитывает детальную информацию по одному артикулу.
    article_stock_summary: {"42": {"Коледино": {"quantity": 5, "region": "Центр"}, ...}, ...}
    article_funnel: {"vendorCode": "ТРЕНД22WHITE", "dl": 49, "orders": 301, ...}
    """
    dl = article_funnel.get("dl", 0)
    ktr, krp = get_ktr_krp(dl)
    orders = article_funnel.get("orders", 0)
    buyouts = article_funnel.get("buyouts", 0)
    buyout_pct = article_funnel.get("buyoutPercent", 0)
    avg_per_day = article_funnel.get("avgOrdersPerDay", 0)

    # Остатки по регионам
    total_stock = 0
    stock_by_region = {}
    for size, warehouses in article_stock_summary.items():
        for wh, info in warehouses.items():
            qty = info.get("quantity", 0)
            region = info.get("region", "Прочее")
            total_stock += qty
            stock_by_region[region] = stock_by_region.get(region, 0) + qty

    # Дней до OOS (общий)
    daily_consumption = avg_per_day * buyout_pct / 100 if buyout_pct > 0 else avg_per_day * 0.22
    days_to_oos = total_stock / daily_consumption if daily_consumption > 0 else 999

    # Дней до OOS по регионам
    days_to_oos_by_region = {}
    for region, share in REGIONS.items():
        stock = stock_by_region.get(region, 0)
        regional_consumption = daily_consumption * share["share"]
        days_to_oos_by_region[region] = stock / regional_consumption if regional_consumption > 0 else 999

    # Потребность поставки по регионам (сколько нужно довезти)
    # Потребность = (Заказы_30дн × Доля × Safety) − Остаток
    need_by_region = {}
    for region_name, data in REGIONS.items():
        target = orders * data["share"] * SAFETY_COEFFICIENT
        stock = stock_by_region.get(region_name, 0)
        need = max(0, round(target - stock))
        need_by_region[region_name] = need

    # Приоритет
    if dl >= 60:
        priority = "SUPPORT"     # Поддержка
    elif dl >= 55:
        priority = "CRITICAL"    # Критическая зона — пробиваем!
    elif dl >= 50:
        priority = "HIGH"        # Высокий приоритет (близко к пробитию)
    elif dl >= 30:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # Есть ли критические нули
    has_critical_zeros = any(
        days < 7 and stock_by_region.get(region, 0) == 0
        for region, days in days_to_oos_by_region.items()
    )

    return {
        "vendorCode": article_funnel.get("vendorCode"),
        "nmId": article_funnel.get("nmId"),
        "dl": dl,
        "ktr": ktr,
        "krp": krp,
        "color": get_dl_color(dl),
        "priority": priority,
        "is_breakthrough": is_breakthrough_zone(dl),
        "orders_4w": orders,
        "buyouts_4w": buyouts,
        "buyoutPercent": buyout_pct,
        "avgOrdersPerDay": avg_per_day,
        "totalStock": total_stock,
        "dailyConsumption": round(daily_consumption, 2),
        "daysToOOS": round(days_to_oos, 1),
        "stockByRegion": stock_by_region,
        "daysToOOSByRegion": {k: round(v, 1) for k, v in days_to_oos_by_region.items()},
        "needByRegion": need_by_region,
        "hasCriticalZeros": has_critical_zeros,
    }


def calc_irp_il(articles: list[dict]) -> dict:
    """
    Рассчитывает общий ИРП и ИЛ на основе данных по артикулам.
    articles: список результатов calc_article_dl
    ИРП = Σ(КРП × Заказы) / Σ(Заказы) × 100
    ИЛ = Σ(КТР × Заказы) / Σ(Заказы)
    """
    total_orders = sum(a.get("orders_4w", 0) for a in articles)
    if total_orders == 0:
        return {"irp": 0, "il": 1.0, "totalOrders": 0}

    weighted_krp = sum(a.get("krp", 0) * a.get("orders_4w", 0) for a in articles)
    weighted_ktr = sum(a.get("ktr", 1.0) * a.get("orders_4w", 0) for a in articles)

    il = round(weighted_ktr / total_orders, 2)
    irp = round(weighted_krp / total_orders, 2)

    return {
        "il": il,
        "irp": irp,
        "totalOrders": total_orders,
        "articles": len(articles),
    }


def calc_daily_velocity(orders: list[dict], days: int = 30) -> dict:
    """
    Скорость заказов по артикулам и регионам.
    Возвращает {"ТРЕНД22WHITE": {"42": {"Центр": 3.2, ...}, ...}, ...}
    """
    real_orders = [o for o in orders if not o.get("isCancel")]

    velocity = {}
    for o in real_orders:
        art = o.get("supplierArticle")
        size = o.get("techSize")
        wh = o.get("warehouseName", "")
        region = WAREHOUSE_TO_REGION.get(wh.lower(), "Прочее")

        if art not in velocity:
            velocity[art] = {}
        if size not in velocity[art]:
            velocity[art][size] = {}
        velocity[art][size][region] = velocity[art][size].get(region, 0) + 1

    # Делим на количество дней
    for art in velocity:
        for size in velocity[art]:
            for region in velocity[art][size]:
                velocity[art][size][region] = round(velocity[art][size][region] / days, 2)

    return velocity


def recommend_shipments(
    articles: list[dict],
    stock_summary: dict,
    velocity: dict,
    factory_stock: dict = None,
    max_boxes: int = 15
) -> list[dict]:
    """
    Генерирует рекомендации по поставкам.
    Приоритет: OOS → пробитие ДЛ без перетарки → поддержка ДЛ.

    Возвращает список коробок:
    [{box_num, region, items: [{barcode, size, color, qty}], total_qty, priority_score}]
    """
    recommendations = []

    for art_data in articles:
        vendor_code = art_data["vendorCode"]
        if vendor_code not in stock_summary:
            continue

        # Определяем тип: костюм или брюки
        is_trousers = "TROUSERS" in vendor_code.upper()
        items_per_box = TROUSERS_PER_BOX if is_trousers else ITEMS_PER_BOX

        # Приоритет отправки
        priority_score = 0
        if art_data["hasCriticalZeros"]:
            priority_score = 100
        elif art_data["is_breakthrough"]:
            priority_score = 80
        elif art_data["dl"] >= 60:
            priority_score = 50
        else:
            priority_score = 30

        # Добавляем вес по объёму заказов
        priority_score += min(art_data["orders_4w"] / 10, 20)

        # Для каждого региона: нужно → регион
        for region in SHIPMENT_PRIORITY:
            need = art_data.get("needByRegion", {}).get(region, 0)

            # Проверка на перетарку: не везём если уже > 30 шт и ДЛ < 60%
            current_stock = art_data.get("stockByRegion", {}).get(region, 0)
            if current_stock > 30 and art_data["dl"] < 60:
                continue  # пропускаем — перетарка

            # Проверка фабрики
            if factory_stock and vendor_code in factory_stock:
                available = sum(factory_stock[vendor_code].values())
                if available <= 0:
                    continue

            if need >= items_per_box * 0.5:  # минимум полкоробки
                boxes_needed = max(1, round(need / items_per_box))
                recommendations.append({
                    "vendorCode": vendor_code,
                    "region": region,
                    "need": need,
                    "currentStock": current_stock,
                    "boxesSuggested": min(boxes_needed, 5),
                    "itemsPerBox": items_per_box,
                    "priorityScore": priority_score,
                    "dl": art_data["dl"],
                    "isBreakthrough": art_data["is_breakthrough"],
                })

    # Сортируем по приоритету
    recommendations.sort(key=lambda x: (-x["priorityScore"], x["dl"]))

    # Ограничиваем количество коробок
    return recommendations[:max_boxes]
