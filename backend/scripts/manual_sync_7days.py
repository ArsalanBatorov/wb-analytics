"""
Ручной запуск синхронизации данных за последние 7 дней.
Запускать из директории /root/wb-analytics/backend/ :
  cd /root/wb-analytics/backend
  python -m scripts.manual_sync_7days
"""
import asyncio
import sys
import os
from datetime import date, timedelta

# Добавляем backend в путь если запускают не из него
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from app.services.wb_api.token_loader import ensure_token

    print("=" * 60)
    print("WB-Analytics: ручной синк за последние 7 дней")
    print("=" * 60)

    if not await ensure_token():
        print("[ERROR] Нет токена WB. Проверьте .env или таблицу settings.")
        return

    from app.services.data_sync import (
        sync_products_and_dimensions,
        sync_daily_stats,
        sync_ad_stats,
        sync_realization_daily,
        sync_stocks,
    )

    today = date.today()
    d7_ago = today - timedelta(days=7)

    print(f"Период: {d7_ago} → {today}\n")

    # 1. Продукты (каталог)
    print("1/5 Синк продуктов (каталог, размеры)...")
    try:
        await sync_products_and_dimensions()
        print("    OK\n")
    except Exception as e:
        print(f"    ОШИБКА: {e}\n")

    # 2. Остатки
    print("2/5 Синк остатков (stocks)...")
    try:
        await sync_stocks()
        print("    OK\n")
    except Exception as e:
        print(f"    ОШИБКА: {e}\n")

    # 3. Дневная статистика — ТОЛЬКО 7 дней
    print("3/5 Синк дневной статистики (product_daily_stats, 7 дней)...")
    try:
        await sync_daily_stats(days=7)
        print("    OK\n")
    except Exception as e:
        print(f"    ОШИБКА: {e}\n")

    # 4. Рекламная статистика — 7 дней
    print("4/5 Синк рекламной статистики (7 дней)...")
    print("    (Внимание: rate-limit WB ~62 сек между кампаниями, может занять время)")
    try:
        await sync_ad_stats(days=7)
        print("    OK\n")
    except Exception as e:
        print(f"    ОШИБКА: {e}\n")

    # 5. Финансовый отчёт (realization)
    print("5/5 Синк финансового отчёта (realization_daily_stats, 7 дней)...")
    try:
        await sync_realization_daily(d7_ago, today)
        print("    OK\n")
    except Exception as e:
        print(f"    ОШИБКА: {e}\n")

    print("=" * 60)
    print("Синк завершён!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
