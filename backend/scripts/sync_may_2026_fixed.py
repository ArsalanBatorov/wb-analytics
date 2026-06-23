#!/usr/bin/env python3
"""
Принудительная синхронизация данных за период 01-11 мая 2026 года.
Исправленная версия с правильной передачей параметров.
"""
import asyncio
import sys
from datetime import date, timedelta

# Добавляем backend в путь для импорта
sys.path.insert(0, '/root/wb-analytics/backend')

from app.services.data_sync import sync_daily_stats, sync_ad_stats, sync_realization_daily


async def sync_daily_stats_fixed(date_from, date_to):
    """Синхронизировать данные за указанный период без конфликта параметров."""
    print(f"Синхронизация основной статистики за период: {date_from} - {date_to}")
    
    # Рассчитываем количество дней для корректной передачи
    days = (date_to - date_from).days + 1
    
    try:
        # Явно передаем все параметры
        await sync_daily_stats(days=days, date_from=date_from, date_to=date_to)
        print(f"✓ Основная статистика синхронизирована за {date_from} - {date_to}")
        return True
    except Exception as e:
        print(f"✗ Ошибка при синхронизации основной статистики за {date_from} - {date_to}: {e}")
        return False


async def sync_ad_stats_fixed(date_from, date_to):
    """Синхронизировать рекламную статистику за указанный период."""
    print(f"Синхронизация рекламной статистики за период: {date_from} - {date_to}")
    
    days = (date_to - date_from).days + 1
    
    try:
        await sync_ad_stats(days=days, date_from=date_from, date_to=date_to)
        print(f"✓ Рекламная статистика синхронизирована за {date_from} - {date_to}")
        return True
    except Exception as e:
        print(f"✗ Ошибка при синхронизации рекламной статистики за {date_from} - {date_to}: {e}")
        return False


async def sync_may_2026_fixed():
    """Синхронизировать данные за период 01-11 мая 2026 года."""
    print("Запуск принудительной синхронизации за период 01-11 мая 2026...")
    
    # Разбиваем на интервалы по 6 дней (чтобы уложиться в лимит 7 дней API)
    periods = [
        (date(2026, 5, 1), date(2026, 5, 6)),   # 6 дней
        (date(2026, 5, 7), date(2026, 5, 11)),  # 5 дней
    ]
    
    success = True
    
    for start_date, end_date in periods:
        print(f"\n--- Обработка периода: {start_date} - {end_date} ---")
        
        # Синхронизация основной статистики
        if not await sync_daily_stats_fixed(start_date, end_date):
            success = False
        
        # Пауза между основной и рекламной статистикой
        await asyncio.sleep(10)
        
        # Синхронизация рекламной статистики
        if not await sync_ad_stats_fixed(start_date, end_date):
            success = False
        
        # Пауза между периодами
        if start_date != periods[-1][0]:
            await asyncio.sleep(30)
    
    # Синхронизация отчета о реализации за весь период
    try:
        await sync_realization_daily(date(2026, 5, 1), date(2026, 5, 11))
        print("✓ Отчет о реализации синхронизирован за весь период")
    except Exception as e:
        print(f"✗ Ошибка при синхронизации отчета о реализации: {e}")
    
    if success:
        print("\nСинхронизация за период 01-11 мая 2026 завершена успешно!")
    else:
        print("\nСинхронизация завершена с ошибками!")
    
    return success


if __name__ == "__main__":
    asyncio.run(sync_may_2026_fixed())