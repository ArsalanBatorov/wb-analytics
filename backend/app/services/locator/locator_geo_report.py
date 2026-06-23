import sqlite3
import pandas as pd
from io import BytesIO
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from app.services.locator.locator_config import get_ktr_krp
from app.services.locator.locator_in_transit_report import get_in_transit_data
from app.services.locator.locator_cache import set_cached_response

DB_PATH = Path(__file__).parent.parent.parent.parent / "locator_cache.db"

def init_geo_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DROP TABLE IF EXISTS geo_size_dl")
        conn.execute("""
            CREATE TABLE geo_size_dl (
                nm_id TEXT,
                vendor_code TEXT,
                size TEXT,
                region TEXT,
                subject TEXT,
                orders_total INTEGER,
                orders_local INTEGER,
                orders_nonlocal INTEGER,
                stock_wb INTEGER,
                dl REAL,
                ktr REAL,
                krp REAL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def parse_geo_report(file_bytes: bytes, date_from: str = None, date_to: str = None) -> int:
    if date_from and date_to:
        set_cached_response("geo_report_period", {"date_from": date_from, "date_to": date_to})
        print(f"Сохранён период: {date_from} - {date_to}")
    else:
        print("Период не передан, будет использован fallback 28 дней")
    
    debug_path = "/root/wb-analytics/debug_geo.xlsx"
    with open(debug_path, "wb") as f:
        f.write(file_bytes)

    try:
        df = pd.read_excel(debug_path, sheet_name="Детальные данные", header=1, engine='openpyxl')
    except Exception as e:
        print(f"Ошибка чтения: {e}")
        return 0

    df.columns = [str(c).strip().lower() for c in df.columns]
    print(f"Столбцы: {list(df.columns)}")

    col_map = {
        'vendor_code': None,
        'nm_id': None,
        'size': None,
        'region': None,
        'orders_total': None,
        'orders_local': None,
        'stock_wb': None,
    }

    for col in df.columns:
        if 'артикул продавца' in col:
            col_map['vendor_code'] = col
        elif 'артикул wb' in col:
            col_map['nm_id'] = col
        elif 'размер' in col:
            col_map['size'] = col
        elif 'регион' in col:
            col_map['region'] = col
        elif 'итого заказов, шт' in col:
            col_map['orders_total'] = col
        elif 'итого заказов по товарам локально, шт' in col:
            col_map['orders_local'] = col
        elif 'остатки склад wb, шт' in col:
            col_map['stock_wb'] = col

    print(f"Маппинг колонок: {col_map}")

    init_geo_db()

    rows_saved = 0
    imported_at = datetime.now().isoformat()
    with sqlite3.connect(str(DB_PATH)) as conn:
        for _, row in df.iterrows():
            nm_id = str(row.get(col_map['nm_id'], ''))
            if not nm_id or nm_id == 'nan':
                continue

            vendor_code = str(row.get(col_map['vendor_code'], ''))
            size = str(row.get(col_map['size'], ''))
            region = str(row.get(col_map['region'], ''))
            orders_total = int(row.get(col_map['orders_total'], 0)) if pd.notna(row.get(col_map['orders_total'], 0)) else 0
            orders_local = int(row.get(col_map['orders_local'], 0)) if pd.notna(row.get(col_map['orders_local'], 0)) else 0
            stock_wb = int(row.get(col_map['stock_wb'], 0)) if pd.notna(row.get(col_map['stock_wb'], 0)) else 0

            orders_nonlocal = orders_total - orders_local
            dl = round(orders_local / orders_total * 100, 2) if orders_total > 0 else 0
            ktr, krp = get_ktr_krp(dl)

            conn.execute("""
                INSERT INTO geo_size_dl
                (nm_id, vendor_code, size, region, orders_total, orders_local, orders_nonlocal, stock_wb, dl, ktr, krp, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nm_id, vendor_code, size, region, orders_total, orders_local, orders_nonlocal, stock_wb, dl, ktr, krp, imported_at))
            rows_saved += 1

    print(f"Сохранено строк: {rows_saved}")
    return rows_saved

def get_geo_size_dl():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM geo_size_dl ORDER BY nm_id, size, region").fetchall()
        return [dict(row) for row in rows]

def get_geo_size_dl_list():
    return get_geo_size_dl()

def get_geo_dl() -> dict:
    from app.services.locator.locator_cache import get_cached_response
    from datetime import date as date_cls
    
    period = get_cached_response("geo_report_period") or {}
    date_from_str = period.get("date_from")
    date_to_str = period.get("date_to")
    
    if date_from_str and date_to_str:
        period_days = max((date_cls.fromisoformat(date_to_str) - date_cls.fromisoformat(date_from_str)).days + 1, 1)
    else:
        period_days = 28

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        geo_rows = conn.execute("SELECT * FROM geo_size_dl ORDER BY nm_id, size, region").fetchall()
        
        try:
            stocks_rows = conn.execute("SELECT nm_id, size, buyout_qty, stock_total, orders_qty, buyout_pct FROM stocks_size_report").fetchall()
            stocks_lookup = {(r["nm_id"], r["size"]): dict(r) for r in stocks_rows}
        except:
            stocks_lookup = {}
        
        try:
            wh_rows = conn.execute("SELECT * FROM stocks_size_warehouse ORDER BY nm_id, size, region").fetchall()
            wh_lookup = defaultdict(list)
            for r in wh_rows:
                wh_lookup[(r["nm_id"], r["size"])].append({
                    "region": r["region"], "warehouse": r["warehouse"],
                    "orders": r["orders_qty"], "buyout": r["buyout_qty"], "stock": r["stock"],
                })
        except:
            wh_lookup = defaultdict(list)

    if not geo_rows:
        return {"articles": [], "imported_at": None, "il": None, "irp": None}

    by_article = defaultdict(lambda: defaultdict(list))
    meta = {}
    for r in geo_rows:
        nm, sz = r["nm_id"], r["size"]
        by_article[nm][sz].append(r)
        if nm not in meta:
            meta[nm] = {"vendor_code": r["vendor_code"], "subject": r["subject"], "imported_at": r["imported_at"]}

    articles = []
    for nm, sizes_dict in by_article.items():
        sizes = []
        art_orders_total = 0
        art_orders_local = 0
        art_stock_total = 0
        
        for sz in sorted(sizes_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            regions = sizes_dict[sz]
            sz_orders = sum(r["orders_total"] for r in regions)
            sz_local = sum(r["orders_local"] for r in regions)
            sz_stock = sum(r["stock_wb"] for r in regions)
            
            dl = round(sz_local / sz_orders * 100, 1) if sz_orders > 0 else None
            ktr, krp = get_ktr_krp(dl) if dl is not None else (None, None)
            
            sk = stocks_lookup.get((nm, sz), {})
            buyout_qty = sk.get("buyout_qty") if sk else None
            stock_wb = sk.get("stock_total") if sk else sz_stock
            orders_wb = sk.get("orders_qty") if sk else None
            
            # Данные о поставках в пути
            in_transit_data = get_in_transit_data(nm, sz)
            effective_stock = (stock_wb if stock_wb is not None else 0) + in_transit_data.get('totalQty', 0)
            
            # OOS для размера с учётом поставок
            if sz_orders > 0 and effective_stock > 0:
                days_to_oos = round(effective_stock / (sz_orders / period_days), 1)
            else:
                days_to_oos = None
            
            # Процент выкупа
            if buyout_qty is not None and orders_wb is not None and orders_wb > 0:
                buyout_pct = round(buyout_qty / orders_wb * 100, 1)
            else:
                buyout_pct = None
            
            by_region_geo = [{"region": r["region"], "orders_total": r["orders_total"], 
                             "orders_local": r["orders_local"], 
                             "dl": round(r["orders_local"] / r["orders_total"] * 100, 1) if r["orders_total"] > 0 else None} 
                            for r in regions]
            
            sizes.append({
                "size": sz, "dl": dl, "ktr": ktr, "krp": krp, 
                "ordersTotal": sz_orders, "ordersLocal": sz_local, "stockWB": stock_wb,
                "buyoutPercent": buyout_pct, "daysToOOS": days_to_oos, 
                "inTransit": in_transit_data,
                "byRegion": by_region_geo, "byWarehouse": wh_lookup.get((nm, sz), [])
            })
            
            art_orders_total += sz_orders
            art_orders_local += sz_local
            art_stock_total += (stock_wb if stock_wb is not None else 0)
        
        # ДЛ артикула
        art_dl = round(art_orders_local / art_orders_total * 100, 1) if art_orders_total > 0 else None
        art_ktr, art_krp = get_ktr_krp(art_dl) if art_dl is not None else (None, None)
        
        # НОВАЯ ЛОГИКА daysToOOS для артикула:
        # суммарный stockWB по всем размерам / (суммарные ordersTotal / period_days)
        if art_orders_total > 0 and art_stock_total > 0:
            art_days_to_oos = round(art_stock_total / (art_orders_total / period_days), 1)
        else:
            art_days_to_oos = None
        
        articles.append({
            "nmId": nm, "vendorCode": meta[nm]["vendor_code"], "subject": meta[nm]["subject"],
            "importedAt": str(meta[nm]["imported_at"]), "dl": art_dl, "ktr": art_ktr, "krp": art_krp,
            "ordersTotal": art_orders_total, "ordersLocal": art_orders_local, "stockWB": art_stock_total,
            "daysToOOS": art_days_to_oos, "ilWeight": 0.0, "sizes": sizes
        })

    total_weighted_krp = sum(s["krp"] * s["ordersTotal"] for a in articles for s in a["sizes"] 
                            if s["krp"] is not None and s["ordersTotal"] > 0)
    for a in articles:
        for s in a["sizes"]:
            s["ilWeight"] = round(s["krp"] * s["ordersTotal"] / total_weighted_krp * 100, 2) if total_weighted_krp > 0 and s.get("krp") is not None else 0.0
        a["ilWeight"] = round(sum(s["ilWeight"] for s in a["sizes"]), 2)

    grand_orders = sum(a["ordersTotal"] for a in articles)
    weighted_ktr = sum(a["ktr"] * a["ordersTotal"] for a in articles if a["ktr"] is not None)
    weighted_krp = sum(a["krp"] * a["ordersTotal"] for a in articles if a["krp"] is not None)
    il = round(weighted_ktr / grand_orders, 2) if grand_orders > 0 else None
    irp = round(weighted_krp / grand_orders, 2) if grand_orders > 0 else None
    
    articles.sort(key=lambda x: -x["ilWeight"])
    
    return {
        "articles": articles, "il": il, "irp": irp, "totalOrders": grand_orders,
        "periodDays": period_days, "dateFrom": date_from_str, "dateTo": date_to_str,
        "importedAt": str(geo_rows[0]["imported_at"]) if geo_rows else None
    }

def get_period_days():
    return 28
