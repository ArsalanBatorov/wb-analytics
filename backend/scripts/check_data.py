# =================== НАЧАЛО ФАЙЛА check_data.py ===================
"""
Диагностика данных перед созданием UI:
  1. cost_price по товарам — нет ли странных значений
  2. сводка по всему периоду в формате, который можно сверить с кабинетом WB
  3. итоги по doc_type (продажи, возвраты, логистика отдельно)
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
        # --- 1. Cost_price по товарам, у которых есть продажи ---
        print("="*100)
        print("1. ТОВАРЫ С ПРОДАЖАМИ И ИХ COST_PRICE")
        print("="*100)
        sql = """
            SELECT
                p.nm_id,
                COALESCE(p.cost_price, 0) AS cost_price,
                COALESCE(p.vendor_code, '') AS vc,
                COUNT(rr.id) FILTER (WHERE rr.doc_type = 'Продажа') AS sales_cnt,
                SUM(rr.quantity) FILTER (WHERE rr.doc_type = 'Продажа') AS qty_sold,
                SUM(rr.retail_price) FILTER (WHERE rr.doc_type = 'Продажа') AS retail_total,
                SUM(rr.ppvz_for_pay) FILTER (WHERE rr.doc_type = 'Продажа') AS payout_total
            FROM products p
            LEFT JOIN realization_records rr ON rr.nm_id = p.nm_id
            GROUP BY p.nm_id, p.cost_price, p.vendor_code
            HAVING COUNT(rr.id) FILTER (WHERE rr.doc_type = 'Продажа') > 0
            ORDER BY qty_sold DESC NULLS LAST
        """
        rows = (await db.execute(text(sql))).mappings().all()
        print(f"{'nm_id':<12} {'vendor_code':<20} {'cost_price':>10} {'qty':>5} "
              f"{'retail_avg':>12} {'payout_avg':>12} {'margin/unit':>12}")
        print("-"*100)
        for r in rows:
            qty = int(r["qty_sold"] or 0)
            if qty == 0:
                continue
            retail_avg = float(r["retail_total"] or 0) / qty
            payout_avg = float(r["payout_total"] or 0) / qty
            margin_per_unit = payout_avg - float(r["cost_price"] or 0)
            cp = float(r["cost_price"] or 0)
            print(f"{r['nm_id']:<12} {(r['vc'] or '')[:18]:<20} {cp:>10.2f} {qty:>5} "
                  f"{retail_avg:>12.2f} {payout_avg:>12.2f} {margin_per_unit:>12.2f}")

        # --- 2. Итоги по типам строк ---
        print()
        print("="*100)
        print("2. ИТОГИ ПО doc_type ЗА ВЕСЬ ПЕРИОД")
        print("="*100)
        sql = """
            SELECT
                COALESCE(NULLIF(doc_type, ''), '(пусто/логистика)') AS dt,
                COUNT(*) AS cnt,
                COALESCE(SUM(quantity), 0) AS qty,
                COALESCE(SUM(retail_price), 0) AS retail_sum,
                COALESCE(SUM(ppvz_for_pay), 0) AS payout_sum,
                COALESCE(SUM(delivery_rub), 0) AS deliv_sum,
                COALESCE(SUM(acquiring_fee), 0) AS acq_sum,
                COALESCE(SUM(storage_fee), 0) AS storage_sum,
                COALESCE(SUM(penalty), 0) AS penalty_sum
            FROM realization_records
            GROUP BY 1
            ORDER BY 1
        """
        rows = (await db.execute(text(sql))).mappings().all()
        for r in rows:
            print(f"\n  {r['dt']} ({r['cnt']} строк, qty={r['qty']})")
            print(f"    retail_price (сумма):  {fmt(r['retail_sum'])}")
            print(f"    ppvz_for_pay (сумма):  {fmt(r['payout_sum'])}")
            print(f"    delivery_rub (сумма):  {fmt(r['deliv_sum'])}")
            print(f"    acquiring_fee (сумма): {fmt(r['acq_sum'])}")
            print(f"    storage_fee (сумма):   {fmt(r['storage_sum'])}")
            print(f"    penalty (сумма):       {fmt(r['penalty_sum'])}")

        # --- 3. Сводка для сверки с финотчётом WB ---
        print()
        print("="*100)
        print("3. СВОДКА ДЛЯ СВЕРКИ С ФИНОТЧЁТОМ WB (Финансы → Финансовый отчёт)")
        print("="*100)
        sql = """
            SELECT
                MIN(sale_dt) AS dmin, MAX(sale_dt) AS dmax,
                SUM(CASE WHEN doc_type='Продажа' THEN ppvz_for_pay ELSE 0 END) AS sales_payout,
                SUM(CASE WHEN doc_type='Возврат' THEN ppvz_for_pay ELSE 0 END) AS returns_payout,
                SUM(CASE WHEN doc_type='Возврат' THEN acquiring_fee ELSE 0 END) AS acq_returns,
                SUM(delivery_rub) AS logistics,
                SUM(storage_fee) AS storage,
                SUM(penalty) AS penalty
            FROM realization_records
        """
        r = (await db.execute(text(sql))).mappings().one()
        net = (
            float(r["sales_payout"] or 0)
            - float(r["returns_payout"] or 0)
            - float(r["acq_returns"] or 0)
            - float(r["logistics"] or 0)
            - float(r["storage"] or 0)
            - float(r["penalty"] or 0)
        )
        print(f"\n  Период: {r['dmin']} → {r['dmax']}\n")
        print(f"  + К перечислению за товары:  {fmt(r['sales_payout'])}")
        print(f"  − Возвраты товаров:          {fmt(r['returns_payout'])}")
        print(f"  − Эквайринг возвратов:       {fmt(r['acq_returns'])}")
        print(f"  − Логистика:                 {fmt(r['logistics'])}")
        print(f"  − Хранение:                  {fmt(r['storage'])}")
        print(f"  − Штрафы и удержания:        {fmt(r['penalty'])}")
        print(f"  ─────────────────────────────────────────────")
        print(f"  = Net payout (без COGS, без рекламы): {fmt(net)}")
        print()
        print("  ↑ Эту цифру сверь с финотчётом WB за тот же период.")
        print("    Если совпадает (±100р) — формула верна, идём делать UI.")
        print("    Если расходится сильно — есть пропущенные удержания.")
        print()

        # --- 4. Подозрительные товары ---
        print("="*100)
        print("4. ПОДОЗРИТЕЛЬНЫЕ ТОВАРЫ (cost_price близок к payout_avg или выше)")
        print("="*100)
        sql = """
            SELECT
                p.nm_id, p.vendor_code, p.cost_price,
                SUM(rr.quantity) FILTER (WHERE rr.doc_type='Продажа') AS qty,
                SUM(rr.ppvz_for_pay) FILTER (WHERE rr.doc_type='Продажа') AS payout
            FROM products p
            JOIN realization_records rr ON rr.nm_id = p.nm_id
            WHERE rr.doc_type = 'Продажа'
            GROUP BY p.nm_id, p.vendor_code, p.cost_price
            HAVING SUM(rr.quantity) FILTER (WHERE rr.doc_type='Продажа') > 0
        """
        rows = (await db.execute(text(sql))).mappings().all()
        print(f"\n{'nm_id':<12} {'vendor_code':<20} {'cost':>10} {'payout/unit':>12} {'cost/payout':>12}")
        print("-"*70)
        warns = []
        for r in rows:
            qty = int(r["qty"] or 0)
            if qty == 0:
                continue
            payout_per_unit = float(r["payout"] or 0) / qty
            cost = float(r["cost_price"] or 0)
            if payout_per_unit <= 0:
                continue
            ratio = cost / payout_per_unit
            if ratio > 0.85 or cost == 0:  # подозрительно: COGS > 85% или cost=0
                warns.append((r['nm_id'], r['vendor_code'] or '', cost, payout_per_unit, ratio))

        if warns:
            for nm, vc, cost, ppu, ratio in warns:
                flag = "❗ cost=0" if cost == 0 else f"❗ cost {ratio*100:.0f}% от payout"
                print(f"{nm:<12} {vc[:18]:<20} {cost:>10.2f} {ppu:>12.2f} {ratio:>12.2%}  {flag}")
        else:
            print("  Подозрительных товаров не найдено")
        print()


if __name__ == "__main__":
    asyncio.run(main())
# =================== КОНЕЦ ФАЙЛА check_data.py ===================
