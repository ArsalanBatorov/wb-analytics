"""
Генератор таблиц упаковки (коробок) для отправки на WB.
"""
from typing import Optional


def generate_packing_list(
    shipments: list[dict],
    stock_summary: dict,
    start_box_num: int = 1
) -> list[dict]:
    """
    Генерирует план упаковки на основе рекомендаций поставок.

    Каждая коробка:
    {
        boxNumber: 1,
        region: "СЗ",
        boxBarcode: "",  # штрихкод короба (будет сгенерирован при маркировке)
        items: [
            {barcode: "2012911996004", size: "42", color: "WHITE", qty: 5},
            ...
        ],
        totalQty: 20,
        brand: "BALGINI",
        type: "2",  # 2 = костюм, 1 = брюки
        status: "planned",
        priorityScore: 100,
    }
    """
    boxes = []
    box_num = start_box_num

    for shipment in shipments:
        vendor_code = shipment["vendorCode"]
        region = shipment["region"]
        boxes_needed = shipment["boxesSuggested"]
        items_per_box = shipment["itemsPerBox"]

        # Определяем цвет и тип по vendorCode
        color = _extract_color(vendor_code)
        item_type = "1" if "TROUSERS" in vendor_code.upper() else "2"

        # Собираем баркоды из stock_summary
        barcodes = _get_barcodes(stock_summary, vendor_code)

        for i in range(boxes_needed):
            box_items = []
            remaining = items_per_box

            # Распределяем по размерам пропорционально
            sizes = sorted(barcodes.keys())
            per_size = max(1, items_per_box // max(len(sizes), 1))

            for size in sizes:
                qty = min(per_size, remaining)
                if qty > 0:
                    box_items.append({
                        "barcode": barcodes[size],
                        "size": size,
                        "color": color,
                        "qty": qty,
                    })
                    remaining -= qty

            if box_items:
                boxes.append({
                    "boxNumber": box_num,
                    "region": region,
                    "vendorCode": vendor_code,
                    "color": color,
                    "boxBarcode": "",  # заполняется при маркировке
                    "items": box_items,
                    "totalQty": items_per_box - remaining,
                    "brand": "BALGINI",
                    "type": item_type,
                    "status": "planned",
                    "priorityScore": shipment.get("priorityScore", 0),
                })
                box_num += 1

    return boxes


def _extract_color(vendor_code: str) -> str:
    """Извлекает цвет из vendor_code."""
    code_upper = vendor_code.upper()
    color_map = {
        "WHITE": "WHITE",
        "DARKBEIGE": "DARKBEIGE",
        "BLACK": "BLACK",
        "BEIGE": "BEIGE",
        "BIEGESINGLE": "BEIGE",
        "IVORYSINGLE": "IVORY",
        "SEAWAVE": "SEAWAVE",
        "PURPLE": "PURPLE",
        "BLUE": "BLUE",
        "GRAY": "GRAY",
        "VINOUS": "VINOUS",
        "GREEN": "GREEN",
        "FUCSHIA": "FUCSHIA",
    }
    for key, val in color_map.items():
        if key in code_upper:
            return val
    return "UNKNOWN"


def _get_barcodes(stock_summary: dict, vendor_code: str) -> dict:
    """
    Извлекает баркоды из stock_summary.
    Возвращает {"42": "2012911996004", "44": "2012911996011", ...}
    """
    art_data = stock_summary.get(vendor_code, {})
    barcodes = {}
    for size, warehouses in art_data.items():
        for wh, info in warehouses.items():
            barcode = info.get("barcode")
            if barcode:
                barcodes[size] = barcode
                break  # берём первый попавшийся баркод для размера
    return barcodes


def format_packing_table(boxes: list[dict]) -> list[dict]:
    """
    Формат таблицы упаковки (как в брифе):
    Баркод | Кол-во | Штрихкод короба | Размер | Цвет | № короба |
    Порядк. | Бренд | Тип | Регион | Статус
    """
    rows = []
    for box in boxes:
        for idx, item in enumerate(box["items"], 1):
            rows.append({
                "barcode": item["barcode"],
                "quantity": item["qty"],
                "boxBarcode": box["boxBarcode"],
                "size": item["size"],
                "color": item["color"],
                "boxNumber": box["boxNumber"],
                "seqNumber": idx,
                "brand": box["brand"],
                "type": box["type"],
                "region": box["region"],
                "status": box["status"],
            })
    return rows
