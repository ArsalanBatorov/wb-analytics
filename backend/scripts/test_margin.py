# =================== НАЧАЛО ФАЙЛА test_margin.py ===================
"""
Тест маржи (источник: realization_daily_stats).

Проверки:
  1. Маржа за один день (по умолчанию 2026-04-19)
  2. Сводка по неделям + сверка с финотчётом WB
  3. Сводка по товарам за весь период
  4. Итоговая сводка через calc_margin_summary
"""
import asyncio
import sys
from datetime import date

from sqlalchemy import text
from app.database import async_session
from app.services.margin_fact import (
    calc_margin_for_day,
    calc_margin_for_period,
    calc_margin_summary,
)


def fmt(x) -> str:
    if x is None:
        x = 0
    return f"{float(x):>13,.2f}".replace(",", " ")


# Известные данные из финотчёта WB для сверки
WB_REPORT = {
    # week_start: (к_перечислению, логистика, хранение, корр_вв, штрафы, итого)
    "2026-03-16": (651_586.78, 159_330.48, 14_012.55, 26_037, 0,    452_191.75),
    "2026-03-23": (450_654.22, 174_491.32, 14_020.83, 27_175, 700,  234_267.07),
    "2026-03-30": (504_067.01, 180_132.91, 14_220.84, 43_114, 530,  265_825.46),
    "2026-04-06": (464_895.37, 183_076.53, 14_221.18, 25_505, 300,  246_737.05),
    "2026-04-13": (385_579.09, 239_177.24, 13_496.66, 122_880, 380,   8_975.49),
    "2026-04-20": (414_703.27, 232_704.52, 13_279.96, 19_408, 160,  147_283.69),
}


async def test_one_day(target: date):
    print(f"\n{'='*100}")
    print(f"ТЕСТ 1: МАРЖА ЗА ОДИН ДЕНЬ — {target}")
    print(f"{'='*100}\n")

    async with async_session() as db:
        rows = await calc_margin_for_day(db, target)

    if not rows:
        print(f"  Нет данных за {target}")
        return

    total_margin = total_revenue = 0.0
    for r in rows:
        if r["nm_id"] == 0:
            tag = " [ОБЩИЕ РАСХОДЫ WB]"
        else:
            tag = ""
        print(f"nm_id: {r['nm_id']}{tag}   Прод/Возв: {r['sales_count']}/{r['returns_count']}")
        print(f"  Выручка                {fmt(r['sales_revenue'])}    Возвратов  {fmt(r['returns_revenue'])}")
        print(f"  Payout продажи         {fmt(r['payout_sales'])}    Payout возв {fmt(r['payout_returns'])}")
        print(f"  Логистика {fmt(r['logistics'])}  Хранение {fmt(r['storage'])}  Корр.ВВ {fmt(r['deduction'])}")
        print(f"  Комиссия  {fmt(r['commission'])}  Эквайринг {fmt(r['acquiring'])}  Штрафы  {fmt(r['penalty'])}")
        print(f"  COGS      {fmt(r['cogs'])}  Реклама  {fmt(r['ad_spend'])}")
        print(f"  Net payout (после удержаний WB)        {fmt(r['net_payout'])}")
        print(f"  МАРЖА (Net − COGS − реклама)           {fmt(r['margin'])}    ({r['margin_pct']:>6.2f}%)")
        print()
        total_margin  += r['margin']
        total_revenue += r['sales_revenue']

    pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
    print(f"{'─'*100}")
    print(f"ИТОГО за {target}:   Выручка {fmt(total_revenue)}   Маржа {fmt(total_margin)} ({pct:.2f}%)")


async def test_by_weeks():
    print(f"\n{'='*100}")
    print(f"ТЕСТ 2: ПО НЕДЕЛЯМ — СВЕРКА С ФИНОТЧЁТОМ WB")
    print(f"{'='*100}\n")

    async with async_session() as db:
        sql = """
            SELECT
                date_trunc('week', stat_date)::date AS w,
                COUNT(DISTINCT stat_date)             AS days,
                SUM(payout_sales - payout_returns)    AS to_pay,
                SUM(logistics_cost + rebill_logistics_cost) AS logistics,
                SUM(storage_cost)   AS storage,
                SUM(deduction_cost) AS deduction,
                SUM(penalty_cost)   AS penalty,
                SUM(net_payout)     AS net_payout,
                SUM(profit_estimate) AS profit
            FROM realization_daily_stats
            GROUP BY 1
            ORDER BY 1
        """
        rows = (await db.execute(text(sql))).mappings().all()

    print(f"{'Неделя':<12} {'Дн':>3} {'К_переч_RDS':>13} {'К_переч_WB':>13} {'Δ':>8}"
          f" {'Лог_RDS':>11} {'Лог_WB':>11} {'Δ':>8}"
          f" {'Корр_RDS':>10} {'Корр_WB':>10} {'Net_RDS':>13}")
    print("-"*150)
    for r in rows:
        wkey = str(r["w"])
        wb = WB_REPORT.get(wkey)
        if wb:
            wb_pay, wb_log, wb_st, wb_corr, wb_pen, wb_total = wb
            d_pay = float(r["to_pay"] or 0) - wb_pay
            d_log = float(r["logistics"] or 0) - wb_log
            print(f"{wkey:<12} {r['days']:>3}"
                  f" {fmt(r['to_pay'])} {fmt(wb_pay)} {d_pay:>+8.0f}"
                  f" {fmt(r['logistics'])} {fmt(wb_log)} {d_log:>+8.0f}"
                  f" {fmt(r['deduction'])} {fmt(wb_corr)} {fmt(r['net_payout'])}")
        else:
            print(f"{wkey:<12} {r['days']:>3}"
                  f" {fmt(r['to_pay'])} {'—':>13} {'—':>8}"
                  f" {fmt(r['logistics'])} {'—':>11} {'—':>8}"
                  f" {fmt(r['deduction'])} {'—':>10} {fmt(r['net_payout'])}")


async def test_by_nm(date_from: date, date_to: date):
    print(f"\n{'='*100}")
    print(f"ТЕСТ 3: МАРЖА ПО ТОВАРАМ ({date_from} → {date_to})")
    print(f"{'='*100}\n")

    async with async_session() as db:
        rows = await calc_margin_for_period(db, date_from, date_to)

    by_nm = {}
    for r in rows:
        nm = r["nm_id"]
        if nm not in by_nm:
            by_nm[nm] = {"sales": 0, "ret": 0, "rev": 0.0, "cogs": 0.0,
                         "log": 0.0, "ded": 0.0, "net": 0.0, "margin": 0.0}
        by_nm[nm]["sales"]  += r["sales_count"]
        by_nm[nm]["ret"]    += r["returns_count"]
        by_nm[nm]["rev"]    += r["sales_revenue"]
        by_nm[nm]["cogs"]   += r["cogs"]
        by_nm[nm]["log"]    += r["logistics"]
        by_nm[nm]["ded"]    += r["deduction"]
        by_nm[nm]["net"]    += r["net_payout"]
        by_nm[nm]["margin"] += r["margin"]

    print(f"{'nm_id':<12} {'Прод':>5} {'Возв':>5} {'Выручка':>13} {'Логист':>11}"
          f" {'Корр.ВВ':>10} {'COGS':>11} {'NetPay':>13} {'Маржа':>13} {'%':>7}")
    print("-"*120)
    for nm in sorted(by_nm.keys(), key=lambda x: -by_nm[x]["rev"]):
        v = by_nm[nm]
        pct = (v["margin"] / v["rev"] * 100) if v["rev"] > 0 else 0
        tag = " ⓘ" if nm == 0 else ""
        print(f"{str(nm)+tag:<12} {v['sales']:>5} {v['ret']:>5}"
              f" {fmt(v['rev'])} {fmt(v['log'])} {fmt(v['ded'])}"
              f" {fmt(v['cogs'])} {fmt(v['net'])} {fmt(v['margin'])}"
              f" {pct:>6.1f}%")


async def test_summary():
    print(f"\n{'='*100}")
    print(f"ТЕСТ 4: ИТОГОВАЯ СВОДКА (calc_margin_summary)")
    print(f"{'='*100}\n")

    async with async_session() as db:
        # Берём весь диапазон из RDS
        r = (await db.execute(text(
            "SELECT MIN(stat_date) AS dmin, MAX(stat_date) AS dmax FROM realization_daily_stats"
        ))).mappings().one()
        dmin, dmax = r["dmin"], r["dmax"]
        s = await calc_margin_summary(db, dmin, dmax)

    print(f"  Период:                {s['date_from']} → {s['date_to']}  ({s['days']} дн)")
    print(f"  Продаж/возвратов:      {s['sales_count']} / {s['returns_count']}  (нетто {s['net_qty']})")
    print()
    print(f"  Выручка:               {fmt(s['sales_revenue'])}")
    print(f"  − Возвраты:            {fmt(s['returns_revenue'])}")
    print(f"  К перечислению:        {fmt(s['to_pay'])}")
    print()
    print(f"  − Логистика:           {fmt(s['logistics'])}")
    print(f"  − Хранение:            {fmt(s['storage'])}")
    print(f"  − Корректировка ВВ:    {fmt(s['deduction'])}")
    print(f"  − Комиссия (нетто):    {fmt(s['commission'])}")
    print(f"  − Эквайринг:           {fmt(s['acquiring'])}")
    print(f"  − Приёмка:             {fmt(s['acceptance'])}")
    print(f"  − Штрафы:              {fmt(s['penalty'])}")
    print(f"  = Net payout:          {fmt(s['net_payout'])}")
    print()
    print(f"  − COGS:                {fmt(s['cogs'])}")
    print(f"  − Реклама:             {fmt(s['ad_spend'])}")
    print(f"  ═══════════════════════════════════════")
    print(f"  МАРЖА:                 {fmt(s['margin'])}    ({s['margin_pct']:>6.2f}%)")


async def main():
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 4, 19)
    await test_one_day(target)
    await test_by_weeks()
    async with async_session() as db:
        r = (await db.execute(text(
            "SELECT MIN(stat_date) AS dmin, MAX(stat_date) AS dmax FROM realization_daily_stats"
        ))).mappings().one()
    await test_by_nm(r["dmin"], r["dmax"])
    await test_summary()
    print()


if __name__ == "__main__":
    asyncio.run(main())
# =================== КОНЕЦ ФАЙЛА test_margin.py ===================
