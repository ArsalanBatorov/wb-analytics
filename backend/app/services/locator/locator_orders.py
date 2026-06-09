import httpx
from datetime import datetime, timedelta
from collections import defaultdict
from app.services.locator.locator_config import SOCKS5_PROXY, WB_API_TOKEN, WAREHOUSE_TO_REGION

async def get_orders_by_size_region(days: int = 28):
    """Собирает заказы за последние N дней, группирует по артикулу, размеру, региону"""
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    
    async with httpx.AsyncClient(proxy=SOCKS5_PROXY, timeout=60, verify=False) as client:
        response = await client.get(
            "https://statistics-api.wildberries.ru/api/v1/supplier/orders",
            params={"dateFrom": date_from},
            headers={"Authorization": WB_API_TOKEN}
        )
        response.raise_for_status()
        orders = response.json()
    
    # Группируем: артикул -> размер -> регион -> количество заказов
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for order in orders:
        if order.get("isCancel"):
            continue  # пропускаем отменённые заказы
        article = order.get("supplierArticle")
        size = order.get("techSize")
        wh = order.get("warehouseName", "")
        region = WAREHOUSE_TO_REGION.get(wh.lower(), "Прочее")
        if article and size:
            stats[article][size][region] += 1
    
    # Преобразуем в удобный формат
    result = {}
    for article, sizes in stats.items():
        result[article] = {}
        for size, regions in sizes.items():
            result[article][size] = dict(regions)
    
    return result
