# =================== НАЧАЛО ФАЙЛА check_rds.py ===================
"""
Проверяем, что лежит в realization_daily_stats — возможно, там уже есть
все недостающие поля (deduction, commission, acceptance и т.д.)
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
        # 1. Колонки таблицы
        print("="*100)
        print("1. КОЛОНКИ realization_daily_stats")
        print("="*100)
        sql = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'realization_daily_stats'
            ORDER BY ordinal_position
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"  {r['column_name']:<30} {r['data_type']}")

        # 2. Сколько строк, диапазон дат
        print()
        print("="*100)
        print("2. ОБЪЁМ ДАННЫХ И ДИАПАЗОН")
        print("="*100)
        sql = """
            SELECT
                COUNT(*) AS total,
                MIN(stat_date) AS dmin,
                MAX(stat_date) AS dmax,
                COUNT(DISTINCT stat_date) AS days,
                COUNT(DISTINCT nm_id) AS nms
            FROM realization_daily_stats
        """
        r = (await db.execute(text(sql))).mappings().one()
        print(f"  Всего строк:       {r['total']}")
        print(f"  Период:            {r['dmin']} → {r['dmax']}")
        print(f"  Уникальных дней:   {r['days']}")
        print(f"  Уникальных nm_id:  {r['nms']}")

        # 3. Несколько примеров строк
        print()
        print("="*100)
        print("3. ПРИМЕРЫ СТРОК (последние 3 дня по nm_id=0 и любому товару)")
        print("="*100)
        sql = """
            SELECT * FROM realization_daily_stats
            WHERE stat_date >= (SELECT MAX(stat_date) - INTERVAL '3 days' FROM realization_daily_stats)
            ORDER BY stat_date DESC, nm_id
            LIMIT 10
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"\n  stat_date={r['stat_date']}  nm_id={r['nm_id']}")
            for k, v in r.items():
                if k in ('id', 'stat_date', 'nm_id', 'updated_at'):
                    continue
                if v is None or (isinstance(v, (int, float)) and v == 0):
                    continue
                print(f"    {k:<25} = {v}")

        # 4. ИТОГО за весь период по всем полям
        print()
        print("="*100)
        print("4. ИТОГО ПО ВСЕМ ПОЛЯМ ЗА ПЕРИОД 18.03-19.04")
        print("="*100)
        sql = """
            SELECT
                COUNT(*) AS rows_count,
                SUM(sales_count)         AS sales_count,
                SUM(sales_revenue)       AS sales_revenue,
                SUM(returns_count)       AS returns_count,
                SUM(returns_revenue)     AS returns_revenue,
                SUM(logistics_cost)      AS logistics_cost,
                SUM(rebill_logistics_cost) AS rebill,
                SUM(storage_cost)        AS storage_cost,
                SUM(acceptance_cost)     AS acceptance_cost,
                SUM(deduction_cost)      AS deduction_cost,
                SUM(penalty_cost)        AS penalty_cost,
                SUM(additional_payment)  AS additional_payment,
                SUM(acquiring_sales)     AS acquiring_sales,
                SUM(acquiring_returns)   AS acquiring_returns,
                SUM(commission_sales)    AS commission_sales,
                SUM(commission_returns)  AS commission_returns,
                SUM(payout_sales)        AS payout_sales,
                SUM(payout_returns)      AS payout_returns,
                SUM(net_payout)          AS net_payout,
                SUM(net_qty)             AS net_qty,
                SUM(cost_price_estimate) AS cogs,
                SUM(profit_estimate)     AS profit_estimate
            FROM realization_daily_stats
            WHERE stat_date BETWEEN '2026-03-18' AND '2026-04-19'
        """
        r = (await db.execute(text(sql))).mappings().one()
        for k, v in r.items():
            if v is not None and (isinstance(v, (int, float)) and v != 0 or k == 'rows_count'):
                print(f"  {k:<25} = {fmt(v) if isinstance(v, (int, float)) and k != 'rows_count' else v}")

        # 5. Сверка: net_payout из этой таблицы — сходится с финотчётом WB?
        print()
        print("="*100)
        print("5. СВЕРКА С ФИНОТЧЁТОМ WB")
        print("="*100)
        print("""
  Финотчёт WB за 16.03-19.04:
    К перечислению за товар:    2 456 782 ₽
    Логистика:                    946 208 ₽
    Хранение:                      69 972 ₽
    Корректировка ВВ:             244 712 ₽
    Прочие удержания:              -5 038 ₽
    Штрафы:                         1 910 ₽
    ИТОГО к оплате:             1 207 990 ₽
        """)
        sql = """
            SELECT
                SUM(payout_sales - payout_returns) AS net_to_pay,
                SUM(logistics_cost + rebill_logistics_cost) AS total_logistics,
                SUM(storage_cost) AS storage,
                SUM(deduction_cost) AS deduction,
                SUM(penalty_cost) AS penalty,
                SUM(acceptance_cost) AS acceptance,
                SUM(net_payout) AS net_payout
            FROM realization_daily_stats
            WHERE stat_date BETWEEN '2026-03-18' AND '2026-04-19'
        """
        r = (await db.execute(text(sql))).mappings().one()
        print(f"  По realization_daily_stats:")
        print(f"    payout_sales − payout_returns:     {fmt(r['net_to_pay'])}")
        print(f"    logistics + rebill:                {fmt(r['total_logistics'])}")
        print(f"    storage_cost:                      {fmt(r['storage'])}")
        print(f"    deduction_cost (прочие):           {fmt(r['deduction'])}")
        print(f"    penalty_cost:                      {fmt(r['penalty'])}")
        print(f"    acceptance_cost (приёмка):         {fmt(r['acceptance'])}")
        print(f"    net_payout (готовое поле):         {fmt(r['net_payout'])}")


if __name__ == "__main__":
    asyncio.run(main())
# =================== КОНЕЦ ФАЙЛА check_rds.py ===================
