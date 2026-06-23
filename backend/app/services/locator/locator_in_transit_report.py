import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent.parent.parent.parent / "locator_cache.db"

def parse_in_transit_excel(file_bytes: bytes) -> List[Dict]:
    """Парсинг Excel с поставками в пути"""
    debug_path = "/root/wb-analytics/debug_in_transit.xlsx"
    with open(debug_path, "wb") as f:
        f.write(file_bytes)
    
    df = pd.read_excel(debug_path, header=0)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Маппинг колонок
    col_map = {
        'nm_id': None,
        'size': None,
        'warehouse': None,
        'quantity': None,
        'eta': None
    }
    
    for col in df.columns:
        if 'артикул' in col or 'nm' in col or 'артикул wb' in col:
            col_map['nm_id'] = col
        elif 'размер' in col or 'size' in col:
            col_map['size'] = col
        elif 'склад' in col or 'warehouse' in col:
            col_map['warehouse'] = col
        elif 'количество' in col or 'quantity' in col or 'шт' in col:
            col_map['quantity'] = col
        elif 'дата' in col or 'eta' in col or 'поступления' in col:
            col_map['eta'] = col
    
    records = []
    for _, row in df.iterrows():
        nm_id = str(row.get(col_map['nm_id'], '')) if col_map['nm_id'] else ''
        if not nm_id or nm_id == 'nan':
            continue
        
        size = str(row.get(col_map['size'], '')) if col_map['size'] else ''
        warehouse = str(row.get(col_map['warehouse'], '')) if col_map['warehouse'] else ''
        quantity = int(row.get(col_map['quantity'], 0)) if col_map['quantity'] and pd.notna(row.get(col_map['quantity'])) else 0
        
        eta_raw = row.get(col_map['eta']) if col_map['eta'] else None
        eta = None
        if pd.notna(eta_raw):
            try:
                if isinstance(eta_raw, datetime):
                    eta = eta_raw.date()
                else:
                    eta_str = str(eta_raw)
                    if '.' in eta_str:
                        eta = datetime.strptime(eta_str, '%d.%m.%Y').date()
                    else:
                        eta = datetime.strptime(eta_str, '%Y-%m-%d').date()
            except:
                eta = None
        
        if quantity > 0:
            records.append({
                'nm_id': nm_id,
                'size': size,
                'warehouse': warehouse,
                'quantity': quantity,
                'eta': eta
            })
    
    return records

def save_in_transit_to_db(records: List[Dict]):
    """Сохранение поставок в БД"""
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM locator_in_transit")
        
        for r in records:
            conn.execute("""
                INSERT OR REPLACE INTO locator_in_transit (nm_id, size, warehouse, quantity, eta, imported_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (r['nm_id'], r['size'], r['warehouse'], r['quantity'], r['eta'], datetime.now().isoformat()))
        
        conn.commit()
    
    print(f"[DEBUG] Сохранено {len(records)} записей в locator_in_transit")

def get_in_transit_data(nm_id: str, size: str) -> Dict:
    """Получение данных о поставках в пути с учётом threshold_days"""
    today = date.today()
    
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        
        # Получаем все поставки для артикула и размера
        rows = conn.execute("""
            SELECT t.nm_id, t.size, t.warehouse, t.quantity, t.eta,
                   COALESCE(w.threshold_days, 7) as threshold_days
            FROM locator_in_transit t
            LEFT JOIN warehouse_regions w ON t.warehouse = w.warehouse_name
            WHERE t.nm_id = ? AND t.size = ?
        """, (nm_id, size)).fetchall()
        
        if not rows:
            return {"totalQty": 0, "batches": []}
        
        # Фильтруем по eta <= сегодня + threshold_days
        filtered_batches = []
        for row in rows:
            eta = datetime.strptime(row['eta'], '%Y-%m-%d').date() if row['eta'] else None
            if eta and eta <= today + timedelta(days=row['threshold_days']):
                filtered_batches.append({
                    'warehouse': row['warehouse'],
                    'quantity': row['quantity'],
                    'eta': eta.isoformat()
                })
        
        total_qty = sum(b['quantity'] for b in filtered_batches)
        
        return {
            "totalQty": total_qty,
            "batches": filtered_batches
        }
