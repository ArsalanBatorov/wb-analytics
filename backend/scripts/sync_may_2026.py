#!/usr/bin/env python3
"""
Принудительная синхронизация данных за май 2026 года.
Используется для восстановления пропущенных данных.
"""
import asyncio
import sys
from datetime import date

# Добавляем backend в путь для импорта
sys.path.insert(0, '/root/wb-analytics/backend')

from app.services.data_sync import sync_daily_stats, sync_ad_stats, sync_realization_daily


async def sync_may_2026():
    """Синхронизировать данные за май 2026 года."""
    print("Запуск принудительной синхронизации за май 2026...")
    
    may_start = date(2026, 5, 1)
    may_end = date(2026, 5, 31)
    
    print(f"Синхронизация статистики за период: {may_start} - {may_end}")
    
    # Синхронизация основной статистики
    try:
        await sync_daily_stats(date_from=may_start, date_to=may_end)
        print("✓ Основная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации основной статистики: {e}")
        return False
    
    # Синхронизация рекламной статистики
    try:
        await sync_ad_stats(date_from=may_start, date_to=may_end)
        print("✓ Рекламная статистика синхронизирована")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации рекламной статистики: {e}")
        # Не прерываем выполнение, так как основная статистика уже получена
    
    # Синхронизация отчета о реализации
    try:
        await sync_realization_daily(may_start, may_end)
        print("✓ Отчет о реализации синхронизирован")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации отчета о реализации: {e}")
    
    print("Синхронизация за май 2026 завершена!")
    return True


if __name__ == "__main__":
    asyncio.run(sync_may_2026())