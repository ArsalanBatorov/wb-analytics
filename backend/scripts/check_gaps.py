# =================== НАЧАЛО ФАЙЛА check_gaps.py ===================
"""
Диагностика расхождений с финотчётом WB:
  1. Какие даты есть в realization_records (нет ли пропусков по неделям)
  2. Полный список колонок таблицы (вдруг есть поля, которые мы не используем)
  3. Распределение по subject_name и любым другим полям
  4. Поиск строк, которые не Продажа/Возврат/пусто (возможно, есть Корректировка)
"""
import asyncio
from sqlalchemy import text
from app.database import async_session


def fmt(x) -> str:
    if x is None:
        x = 0
    return f"{float(x):>14,.2f}".replace(",", " ")


async def main():
    async with async_session() as db:
        # --- 1. Все колонки realization_records ---
        print("="*100)
        print("1. ВСЕ КОЛОНКИ realization_records")
        print("="*100)
        sql = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'realization_records'
            ORDER BY ordinal_position
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"  {r['column_name']:<25} {r['data_type']}")

        # --- 2. Уникальные значения doc_type (вдруг есть Корректировка) ---
        print()
        print("="*100)
        print("2. УНИКАЛЬНЫЕ ЗНАЧЕНИЯ doc_type")
        print("="*100)
        sql = """
            SELECT
                COALESCE(NULLIF(doc_type, ''), '<пусто>') AS dt,
                COUNT(*) AS cnt
            FROM realization_records
            GROUP BY doc_type
            ORDER BY cnt DESC
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"  {r['dt']:<30} {r['cnt']:>6} строк")

        # --- 3. Уникальные значения subject_name ---
        print()
        print("="*100)
        print("3. УНИКАЛЬНЫЕ ЗНАЧЕНИЯ subject_name (топ 20)")
        print("="*100)
        sql = """
            SELECT
                COALESCE(NULLIF(subject_name, ''), '<пусто>') AS sn,
                COUNT(*) AS cnt
            FROM realization_records
            GROUP BY subject_name
            ORDER BY cnt DESC
            LIMIT 20
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"  {r['sn']:<40} {r['cnt']:>6}")

        # --- 4. Распределение записей по неделям ---
        print()
        print("="*100)
        print("4. РАСПРЕДЕЛЕНИЕ ПО НЕДЕЛЯМ (sale_dt)")
        print("="*100)
        sql = """
            SELECT
                date_trunc('week', sale_dt)::date AS week_start,
                COUNT(*) AS cnt,
                COUNT(DISTINCT sale_dt) AS days_with_data,
                SUM(CASE WHEN doc_type='Продажа' THEN ppvz_for_pay ELSE 0 END) AS sales,
                SUM(delivery_rub) AS logistics
            FROM realization_records
            WHERE sale_dt IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """
        rows = (await db.execute(text(sql))).mappings().all()
        print(f"  {'Неделя':<12} {'Строк':>6} {'Дней':>5} {'Продажи':>14} {'Логистика':>14}")
        print("  " + "-"*60)
        for r in rows:
            print(f"  {str(r['week_start']):<12} {r['cnt']:>6} {r['days_with_data']:>5}"
                  f" {fmt(r['sales'])} {fmt(r['logistics'])}")

        # --- 5. Все строки, где есть penalty или ненулевой acquiring_fee при пустом doc_type ---
        print()
        print("="*100)
        print("5. ПРИМЕРЫ СТРОК С НЕОБЫЧНЫМ ДОКТИПОМ (если есть)")
        print("="*100)
        sql = """
            SELECT *
            FROM realization_records
            WHERE doc_type NOT IN ('Продажа', 'Возврат', '')
               OR doc_type IS NULL AND ppvz_for_pay <> 0
            LIMIT 10
        """
        rows = (await db.execute(text(sql))).mappings().all()
        if rows:
            for r in rows:
                print(f"  rrd_id={r['rrd_id']} doc_type='{r['doc_type']}' "
                      f"ppvz={r['ppvz_for_pay']} delivery={r['delivery_rub']} "
                      f"sale_dt={r['sale_dt']} subject='{r.get('subject_name', '')}'")
        else:
            print("  Нет — все строки имеют стандартный doc_type")

        # --- 6. Сводка по ключевым полям, которые могут содержать "корректировку ВВ" ---
        print()
        print("="*100)
        print("6. ПРОВЕРКА: суммы по всем числовым полям за период 18.03-19.04")
        print("="*100)
        sql = """
            SELECT
                SUM(retail_price)        AS retail_price,
                SUM(retail_amount)       AS retail_amount,
                SUM(ppvz_for_pay)        AS ppvz_for_pay,
                SUM(delivery_rub)        AS delivery_rub,
                SUM(acquiring_fee)       AS acquiring_fee,
                SUM(storage_fee)         AS storage_fee,
                SUM(penalty)             AS penalty,
                COUNT(*)                 AS total_rows
            FROM realization_records
            WHERE sale_dt BETWEEN '2026-03-18' AND '2026-04-19'
        """
        r = (await db.execute(text(sql))).mappings().one()
        print(f"  total_rows:    {r['total_rows']}")
        print(f"  retail_price:  {fmt(r['retail_price'])}")
        print(f"  retail_amount: {fmt(r['retail_amount'])}")
        print(f"  ppvz_for_pay:  {fmt(r['ppvz_for_pay'])}")
        print(f"  delivery_rub:  {fmt(r['delivery_rub'])}")
        print(f"  acquiring_fee: {fmt(r['acquiring_fee'])}")
        print(f"  storage_fee:   {fmt(r['storage_fee'])}")
        print(f"  penalty:       {fmt(r['penalty'])}")

        # --- 7. Где живёт data_sync — посмотрим, как мы тянем отчёт ---
        print()
        print("="*100)
        print("7. ИТОГО: ЧЕГО НЕ ХВАТАЕТ ОТНОСИТЕЛЬНО ФИНОТЧЁТА WB")
        print("="*100)
        print("""
  WB финотчёт за 16.03-19.04 показывает:
    К перечислению:           2 456 782 ₽
    Логистика:                  946 208 ₽
    Хранение:                    69 972 ₽
    Корректировка Вознагр.ВВ:   244 712 ₽  ← ЭТОГО НЕТ В НАШЕЙ ФОРМУЛЕ
    Прочие удержания:            -5 038 ₽  ← И ЭТОГО ТОЖЕ
    Штрафы:                       1 910 ₽
    ИТОГО к оплате:           1 207 990 ₽

  У нас в БД:
    ppvz_for_pay (продажи):   2 094 577 ₽  → дыра ~362 тыс
    delivery_rub:               673 298 ₽  → дыра ~273 тыс
    storage_fee:                 47 932 ₽  → дыра ~22 тыс
    Net payout:                 776 608 ₽  → итог расходится на 431 тыс

  ВОЗМОЖНЫЕ ПРИЧИНЫ:
    a) Не все недели/дни синхронизированы (см. раздел 4 — пропуски?)
    b) Часть строк отчёта не подтягивается из WB API
    c) В realization_records нет колонок для:
       - Корректировка вознаграждения ВВ (separate WB API field?)
       - Прочие удержания
    d) WB API возвращает агрегаты иначе, чем показывает в кабинете
        """)


if __name__ == "__main__":
    asyncio.run(main())
# =================== КОНЕЦ ФАЙЛА check_gaps.py ===================
