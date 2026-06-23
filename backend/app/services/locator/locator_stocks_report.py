import sqlite3
import pandas as pd
from io import BytesIO
from pathlib import Path
from app.services.locator.locator_config import WAREHOUSE_TO_REGION

DB_PATH = Path(__file__).parent.parent.parent.parent / "locator_cache.db"

def init_stocks_report_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks_size_report (
                nm_id TEXT,
                size TEXT,
                orders_qty INTEGER,
                buyout_qty INTEGER,
                stock_total INTEGER,
                buyout_pct REAL,
                PRIMARY KEY (nm_id, size)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks_size_warehouse (
                nm_id TEXT,
                size TEXT,
                warehouse TEXT,
                region TEXT,
                orders_qty INTEGER,
                buyout_qty INTEGER,
                stock INTEGER
            )
        """)
        conn.execute("DELETE FROM stocks_size_report")
        conn.execute("DELETE FROM stocks_size_warehouse")

def parse_stocks_report(file_bytes: bytes) -> dict:
    df = pd.read_excel(BytesIO(file_bytes), sheet_name="Sheet1", header=1)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    result = {}
    warehouse_rows = []

    for idx, row in df.iterrows():
        article = str(row.get("артикул wb", ""))
        if not article or article == "nan":
            continue
        
        size = str(row.get("размер", ""))
        warehouse = str(row.get("склад", ""))
        
        # Читаем оригинальные значения (отрицательные тоже сохраняем)
        orders = int(row.get("шт.", 0)) if pd.notna(row.get("шт.", 0)) else 0
        buyouts = int(row.get("выкупили, шт.", 0)) if pd.notna(row.get("выкупили, шт.", 0)) else 0
        stock = int(row.get("текущий остаток, шт.", 0)) if pd.notna(row.get("текущий остаток, шт.", 0)) else 0
        
        region = WAREHOUSE_TO_REGION.get(warehouse.lower(), "Прочее")
        
        key = f"{article}_{size}"
        if key not in result:
            result[key] = {"orders": 0, "buyouts": 0, "stock": 0}
        result[key]["orders"] += orders
        result[key]["buyouts"] += buyouts  # Отрицательные значения сохраняются
        result[key]["stock"] += stock

        warehouse_rows.append({
            "nm_id": article,
            "size": size,
            "warehouse": warehouse,
            "region": region,
            "orders_qty": orders,
            "buyout_qty": buyouts,  # Отрицательные значения сохраняются
            "stock": stock,
        })

    summary = []
    for key, data in result.items():
        nm_id, size = key.split("_", 1)
        # Процент выкупа может быть отрицательным, если возвраты превышают заказы
        buyout_pct = round(data["buyouts"] / data["orders"] * 100, 2) if data["orders"] > 0 else 0
        summary.append({
            "nm_id": nm_id,
            "size": size,
            "orders_qty": data["orders"],
            "buyout_qty": data["buyouts"],  # Отрицательные значения сохраняются
            "stock_total": data["stock"],
            "buyout_pct": buyout_pct,
        })
    
    return {"summary": summary, "warehouse": warehouse_rows}

def save_stocks_report(summary_rows: list, warehouse_rows: list):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM stocks_size_report")
        conn.execute("DELETE FROM stocks_size_warehouse")
        
        for r in summary_rows:
            conn.execute(
                "INSERT INTO stocks_size_report (nm_id, size, orders_qty, buyout_qty, stock_total, buyout_pct) VALUES (?, ?, ?, ?, ?, ?)",
                (r["nm_id"], r["size"], r["orders_qty"], r["buyout_qty"], r["stock_total"], r["buyout_pct"])
            )
        for w in warehouse_rows:
            conn.execute(
                "INSERT INTO stocks_size_warehouse (nm_id, size, warehouse, region, orders_qty, buyout_qty, stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (w["nm_id"], w["size"], w["warehouse"], w["region"], w["orders_qty"], w["buyout_qty"], w["stock"])
            )
        conn.commit()
