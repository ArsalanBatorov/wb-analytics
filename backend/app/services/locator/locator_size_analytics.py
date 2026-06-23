import httpx
import asyncio
import json
import csv
import io
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.services.locator.locator_config import SOCKS5_PROXY, WB_API_TOKEN

ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"

async def create_detail_report(nm_ids: List[int], days: int = 28) -> Optional[str]:
    """Создаёт задание на генерацию CSV-отчёта DETAIL_HISTORY_REPORT и возвращает UUID."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    async with httpx.AsyncClient(proxy=SOCKS5_PROXY, timeout=60, verify=False) as client:
        # Генерируем UUID для отчёта
        report_uuid = f"locator_{int(datetime.now().timestamp())}"
        
        body = {
            "uuid": report_uuid,
            "type": "DETAIL_HISTORY_REPORT",
            "period": {"start": start_date, "end": end_date},
            "filter": {
                "nmIds": nm_ids,
                "detailLevel": "nm"
            }
        }
        
        response = await client.post(
            f"{ANALYTICS_URL}/api/v2/nm-report/downloads",
            headers={"Authorization": WB_API_TOKEN, "Content-Type": "application/json"},
            json=body
        )
        if response.status_code == 200:
            return report_uuid
        return None

async def get_report_status(report_uuid: str) -> str:
    """Проверяет статус генерации отчёта. Возвращает 'completed', 'error' или 'pending'."""
    async with httpx.AsyncClient(proxy=SOCKS5_PROXY, timeout=60, verify=False) as client:
        response = await client.get(
            f"{ANALYTICS_URL}/api/v2/nm-report/downloads",
            params={"uuid": report_uuid},
            headers={"Authorization": WB_API_TOKEN}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("status", "pending")
        return "error"

async def download_report(report_uuid: str) -> Optional[bytes]:
    """Скачивает готовый отчёт (ZIP-архив)."""
    async with httpx.AsyncClient(proxy=SOCKS5_PROXY, timeout=120, verify=False) as client:
        response = await client.get(
            f"{ANALYTICS_URL}/api/v2/nm-report/downloads/download",
            params={"uuid": report_uuid},
            headers={"Authorization": WB_API_TOKEN}
        )
        if response.status_code == 200:
            return response.content
        return None

def parse_size_data_from_csv(csv_content: str) -> Dict[str, Dict[str, any]]:
    """
    Парсит CSV и возвращает данные по размерам.
    Формат возврата: { "nmId": { "size": { "ordersCount": 10, "buyoutsCount": 5, "localizationPercent": 53.2 } } }
    """
    import csv
    from io import StringIO
    
    result = {}
    reader = csv.DictReader(StringIO(csv_content))
    
    for row in reader:
        # Ищем колонки с размерами (techSize, size, размер)
        size_col = None
        for col in ["techSize", "size", "размер", "Size"]:
            if col in row:
                size_col = col
                break
        
        if not size_col:
            continue
            
        size = row.get(size_col, "").strip()
        if not size:
            continue
            
        nm_id = row.get("nmId", "")
        if not nm_id:
            continue
            
        orders = int(row.get("ordersCount", row.get("orderCount", 0)))
        buyouts = int(row.get("buyoutsCount", row.get("buyoutCount", 0)))
        dl = float(row.get("localizationPercent", row.get("localization", 0)))
        
        if nm_id not in result:
            result[nm_id] = {}
        
        result[nm_id][size] = {
            "orders4w": orders,
            "buyouts4w": buyouts,
            "buyoutPercent": round(buyouts / max(orders, 1) * 100, 1) if orders > 0 else 0,
            "dl": dl,
        }
    
    return result

async def get_size_analytics_by_nm_id(nm_ids: List[int], force_refresh: bool = False) -> Dict[str, Dict[str, any]]:
    """
    Главная функция: получает размерную аналитику для списка nmIds.
    Возвращает { "nmId": { "size": { "dl": 53.2, "orders4w": 10, "buyoutPercent": 50 } } }
    """
    # Проверяем кэш (можно добавить позже)
    
    # Создаём отчёт
    report_uuid = await create_detail_report(nm_ids)
    if not report_uuid:
        return {}
    
    # Ждём готовности (максимум 30 секунд)
    for _ in range(15):
        await asyncio.sleep(2)
        status = await get_report_status(report_uuid)
        if status == "completed":
            break
        if status == "error":
            return {}
    
    # Скачиваем отчёт
    zip_content = await download_report(report_uuid)
    if not zip_content:
        return {}
    
    # Распаковываем ZIP и читаем CSV
    import zipfile
    from io import BytesIO
    
    with zipfile.ZipFile(BytesIO(zip_content)) as zf:
        for filename in zf.namelist():
            if filename.endswith(".csv"):
                csv_content = zf.read(filename).decode("utf-8-sig")
                return parse_size_data_from_csv(csv_content)
    
    return {}
