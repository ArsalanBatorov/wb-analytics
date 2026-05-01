# =================== НАЧАЛО ФАЙЛА check_rds_gaps.py ===================
"""
Проверка realization_daily_stats:
  1. Какие даты пропущены в данных
  2. Распределение по неделям (для сверки с финотчётом WB)
  3. Есть ли nm_id=0 строки (агрегатные)
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
        # 1. Распределение по неделям
        print("="*100)
        print("1. RDS ПО НЕДЕЛЯМ (для сверки с финотчётом WB)")
        print("="*100)
        sql = """
            SELECT
                date_trunc('week', stat_date)::date AS week_start,
                COUNT(DISTINCT stat_date) AS days,
                COUNT(*) AS rows,
                SUM(sales_revenue) AS sales,
                SUM(payout_sales - payout_returns) AS net_to_pay,
                SUM(logistics_cost + rebill_logistics_cost) AS total_logistics,
                SUM(storage_cost) AS storage,
                SUM(deduction_cost) AS deduction,
                SUM(penalty_cost) AS penalty,
                SUM(net_payout) AS net_payout,
                SUM(profit_estimate) AS profit
            FROM realization_daily_stats
            GROUP BY 1
            ORDER BY 1
        """
        rows = (await db.execute(text(sql))).mappings().all()
        print(f"\n{'Неделя':<12} {'Дн':>3} {'Строк':>5} {'К перечислению':>16} "
              f"{'Логистика':>14} {'Хранение':>12} {'Корр.ВВ':>12} {'Net pay':>14} {'Profit':>14}")
        print("-"*120)
        for r in rows:
            print(f"{str(r['week_start']):<12} {r['days']:>3} {r['rows']:>5}"
                  f" {fmt(r['net_to_pay'])} {fmt(r['total_logistics'])}"
                  f" {fmt(r['storage'])} {fmt(r['deduction'])}"
                  f" {fmt(r['net_payout'])} {fmt(r['profit'])}")

        # 2. Все даты в RDS (поиск пропусков)
        print()
        print("="*100)
        print("2. ВСЕ ДАТЫ В RDS")
        print("="*100)
        sql = """
            SELECT stat_date, COUNT(*) AS rows, SUM(net_payout) AS np
            FROM realization_daily_stats
            GROUP BY stat_date
            ORDER BY stat_date
        """
        rows = (await db.execute(text(sql))).mappings().all()
        print(f"\n{'Дата':<12} {'Строк':>6} {'Net payout':>14}")
        for r in rows:
            print(f"{str(r['stat_date']):<12} {r['rows']:>6} {fmt(r['np'])}")

        # 3. nm_id = 0 строки (агрегатные расходы, не привязанные к товарам)
        print()
        print("="*100)
        print("3. СТРОКИ С nm_id=0 (общие расходы)")
        print("="*100)
        sql = """
            SELECT stat_date, logistics_cost, rebill_logistics_cost, storage_cost,
                   deduction_cost, penalty_cost, net_payout, profit_estimate
            FROM realization_daily_stats
            WHERE nm_id = 0
            ORDER BY stat_date
        """
        rows = (await db.execute(text(sql))).mappings().all()
        if rows:
            print(f"\n{'Дата':<12} {'Логист':>12} {'Rebill':>10} {'Хранение':>12}"
                  f" {'Корр.ВВ':>12} {'Штрафы':>10} {'Net':>14}")
            for r in rows:
                print(f"{str(r['stat_date']):<12}"
                      f" {fmt(r['logistics_cost'])} {fmt(r['rebill_logistics_cost'])}"
                      f" {fmt(r['storage_cost'])} {fmt(r['deduction_cost'])}"
                      f" {fmt(r['penalty_cost'])} {fmt(r['net_payout'])}")
        else:
            print("  Нет строк с nm_id=0")


if __name__ == "__main__":
    asyncio.run(main())
# =================== КОНЕЦ ФАЙЛА check_rds_gaps.py ===================
