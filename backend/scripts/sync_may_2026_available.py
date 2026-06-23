#!/usr/bin/env python3
"""
Принудительная синхронизация данных за доступный период мая 2026 года.
WB API позволяет запрашивать данные только за последние 30 дней, и период не должен превышать 7 дней.
"""
import asyncio
import sys
from datetime import date, timedelta

# Добавляем backend в путь для импорта
sys.path.insert(0, '/root/wb-analytics/backend')

from app.services.data_sync import sync_daily_stats, sync_ad_stats, sync_realization_daily


async def sync_available_period():
    """Синхронизировать данные за доступный период (последние 7 дней)."""
    today = date(2026, 5, 12)  # Текущая дата
    start_date = today - timedelta(days=6)  # 6 мая 2026
    end_date = today - timedelta(days=1)    # 11 мая 2026
    
    print(f"Синхронизация за доступный период: {start_date} - {end_date}")
    
    try:
        await sync_daily_stats(days=7, date_from=start_date, date_to=end_date)
        print("✓ Основная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации основной статистики: {e}")
        return False
    
    try:
        await sync_ad_stats(days=7, date_from=start_date, date_to=end_date)
        print("✓ Рекламная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации рекламной статистики: {e}")
    
    try:
        await sync_realization_daily(start_date, end_date)
        print("✓ Отчет о реализации синхронизирован")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации отчета о реализации: {e}")
    
    print("Синхронизация за доступный период завершена!")
    return True


if __name__ == "__main__":
    asyncio.run(sync_available_period())