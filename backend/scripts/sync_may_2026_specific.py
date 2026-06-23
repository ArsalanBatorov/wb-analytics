#!/usr/bin/env python3
"""
Принудительная синхронизация данных за период 01-11 мая 2026 года.
Используется для восстановления пропущенных данных.
"""
import asyncio
import sys
from datetime import date

# Добавляем backend в путь для импорта
sys.path.insert(0, '/root/wb-analytics/backend')

from app.services.data_sync import sync_daily_stats, sync_ad_stats, sync_realization_daily


async def sync_may_2026_specific():
    """Синхронизировать данные за период 01-11 мая 2026 года."""
    print("Запуск принудительной синхронизации за период 01-11 мая 2026...")
    
    start_date = date(2026, 5, 1)
    end_date = date(2026, 5, 11)
    
    print(f"Синхронизация статистики за период: {start_date} - {end_date}")
    
    # Синхронизация основной статистики
    try:
        await sync_daily_stats(date_from=start_date, date_to=end_date)
        print("✓ Основная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации основной статистики: {e}")
        return False
    
    # Синхронизация рекламной статистики
    try:
        await sync_ad_stats(date_from=start_date, date_to=end_date)
        print("✓ Рекламная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации рекламной статистики: {e}")
        # Не прерываем выполнение, так как основная статистика уже получена
    
    # Синхронизация отчета о реализации
    try:
        await sync_realization_daily(start_date, end_date)
        print("✓ Отчет о реализации синхронизирован")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации отчета о реализации: {e}")
    
    print("Синхронизация за период 01-11 мая 2026 завершена!")
    return True


if __name__ == "__main__":
    asyncio.run(sync_may_2026_specific())