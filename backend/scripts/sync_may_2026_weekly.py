#!/usr/bin/env python3
"""
Принудительная синхронизация данных за период 01-11 мая 2026 года.
Разбита на недельные интервалы из-за ограничений WB API (макс. 7 дней).
"""
import asyncio
import sys
from datetime import date, timedelta

# Добавляем backend в путь для импорта
sys.path.insert(0, '/root/wb-analytics/backend')

from app.services.data_sync import sync_daily_stats, sync_ad_stats, sync_realization_daily


async def sync_weekly_period(start_date, end_date):
    """Синхронизировать данные за недельный период."""
    print(f"Синхронизация за период: {start_date} - {end_date}")
    
    # Синхронизация основной статистики
    try:
        await sync_daily_stats(date_from=start_date, date_to=end_date)
        print(f"✓ Основная статистика синхронизирована за {start_date} - {end_date}")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации основной статистики за {start_date} - {end_date}: {e}")
        return False
    
    # Синхронизация рекламной статистики
    try:
        await sync_ad_stats(date_from=start_date, date_to=end_date)
        print(f"✓ Рекламная статистика синхронизирована за {start_date} - {end_date}")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации рекламной статистики за {start_date} - {end_date}: {e}")
    
    return True


async def sync_may_2026_weekly():
    """Синхронизировать данные за период 01-11 мая 2026 года по неделям."""
    print("Запуск принудительной синхронизации за период 01-11 мая 2026 (по неделям)...")
    
    # Разбиваем период 01-11 мая на интервалы по максимум 7 дней
    periods = [
        (date(2026, 5, 1), date(2026, 5, 7)),   # Первая неделя
        (date(2026, 5, 8), date(2026, 5, 11)),  # Вторая неделя (4 дня)
    ]
    
    success = True
    for start_date, end_date in periods:
        if not await sync_weekly_period(start_date, end_date):
            success = False
        # Добавляем паузу между запросами
        await asyncio.sleep(10)
    
    # Синхронизация отчета о реализации за весь период
    try:
        await sync_realization_daily(date(2026, 5, 1), date(2026, 5, 11))
        print("✓ Отчет о реализации синхронизирован за весь период")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации отчета о реализации: {e}")
    
    if success:
        print("Синхронизация за период 01-11 мая 2026 завершена успешно!")
    else:
        print("Синхронизация завершена с ошибками!")
    
    return success


if __name__ == "__main__":
    asyncio.run(sync_may_2026_weekly())