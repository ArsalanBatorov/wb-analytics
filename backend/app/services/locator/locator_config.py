"""
Конфигурация Locator. Только константы вне API.
Баркоды, размеры, цвета — динамически из WB API.
"""
import os

# ============================================================
# PROXY
# ============================================================
SOCKS5_PROXY = os.getenv("SOCKS5_PROXY", "socks5://100.85.139.114:1080")

# ============================================================
# WB API TOKEN (из .env)
# ============================================================
WB_API_TOKEN = os.getenv("WB_API_TOKEN", "")

# ============================================================
# ФИЛЬТР: какие артикулы отслеживаем
# ============================================================
TRACKED_ARTICLES = [
    # Костюмы (двойки)
    "ТРЕНД22WHITE",
    "ТРЕНД22DARKBEIGE",
    "ТРЕНД22BLACK",
    "ТРЕНД22BEIGE",
    "ТРЕНД22BIEGESINGLE",
    # Жакеты отдельно
    "ТРЕНД22JACKETWHITE",
    "ТРЕНД22JACKETBLACK",
    "ТРЕНД22JACKETDARKBEIGE",
    "ТРЕНД22JACKETBIEGESINGLE",
    # Брюки отдельно
    "ТРЕНД22TROUSERSBLACK",
    "ТРЕНД22TROUSERSWHITE",
    "ТРЕНД22TROUSERSDARKBEIGE",
]

# Фильтр по категории (из API поле subject)
TRACKED_SUBJECTS = ["Костюмы", "Пиджаки", "Брюки"]

# ============================================================
# КОНСТАНТЫ БРЕНДА
# ============================================================
TURNOVER_DAYS = 30           # оборачиваемость без буфера
TURNOVER_DAYS_BUFFER = 45    # с буфером 20%
SAFETY_COEFFICIENT = 1.3     # страховой коэффициент
JUNE_SEASONALITY = 2.0       # просадка июня ×2
ITEMS_PER_BOX = 20           # костюмов в короб 60×40×40
TROUSERS_PER_BOX = 40        # брюк в короб 60×40×40
PACKING_SPEED = 45           # шт/день средняя скорость упаковки

# ============================================================
# РЕГИОНЫ И СКЛАДЫ (приоритет отправки)
# ============================================================
REGIONS = {
    "СЗ":          {"share": 0.105, "priority": 1, "warehouses": ["Санкт-Петербург", "Шушары"]},
    "Приволжье":   {"share": 0.14,  "priority": 2, "warehouses": ["Казань", "Новосемейкино", "Тула"]},
    "Урал":        {"share": 0.08,  "priority": 3, "warehouses": ["Екатеринбург", "Перспективная"]},
    "Юг":          {"share": 0.17,  "priority": 4, "warehouses": ["Краснодар", "Невинномысск", "Волгоград"]},
    "Центр":       {"share": 0.33,  "priority": 5, "warehouses": ["Коледино", "Электросталь", "Подольск", "Рязань"]},
    "ДВ/Сибирь":   {"share": 0.12,  "priority": 6, "warehouses": ["Хабаровск", "Новосибирск"]},
}

WAREHOUSE_TO_REGION = {}
for region_name, data in REGIONS.items():
    for wh in data["warehouses"]:
        WAREHOUSE_TO_REGION[wh.lower()] = region_name

SHIPMENT_PRIORITY = sorted(REGIONS.keys(), key=lambda r: REGIONS[r]["priority"])

# Сроки доставки до WB (дни)
DELIVERY_DAYS = {
    "СЗ": 1, "Центр": 6, "Приволжье": 8,
    "Урал": 8, "Юг": 8, "ДВ/Сибирь": 10,
}

# ============================================================
# ТАБЛИЦА КТР / КРП (эталон WB)
# ============================================================
KTR_KRP_TABLE = [
    (95.00, 100.00, 0.50, 0.00),
    (90.00, 94.99,  0.60, 0.00),
    (85.00, 89.99,  0.70, 0.00),
    (80.00, 84.99,  0.80, 0.00),
    (75.00, 79.99,  0.90, 0.00),
    (70.00, 74.99,  1.00, 0.00),
    (65.00, 69.99,  1.00, 0.00),
    (60.00, 64.99,  1.00, 0.00),
    (55.00, 59.99,  1.05, 2.00),   # ← критическая зона
    (50.00, 54.99,  1.10, 2.05),
    (45.00, 49.99,  1.20, 2.05),
    (40.00, 44.99,  1.30, 2.10),
    (35.00, 39.99,  1.40, 2.10),
    (30.00, 34.99,  1.50, 2.15),
    (25.00, 29.99,  1.55, 2.20),
    (20.00, 24.99,  1.60, 2.25),
    (15.00, 19.99,  1.70, 2.30),
    (10.00, 14.99,  1.75, 2.35),
    (5.00,  9.99,   1.80, 2.45),
    (0.00,  4.99,   2.00, 2.50),
]


def get_ktr_krp(dl: float) -> tuple:
    """(КТР, КРП) для доли локализации."""
    for dl_min, dl_max, ktr, krp in KTR_KRP_TABLE:
        if dl_min <= dl <= dl_max:
            return ktr, krp
    return 2.00, 2.50


def is_breakthrough_zone(dl: float) -> bool:
    """ДЛ 55-59% — зона пробития порога 60%."""
    return 55.0 <= dl < 60.0


def get_dl_color(dl: float) -> str:
    """green / yellow / grey / red"""
    if dl >= 60: return "green"
    if dl >= 50: return "yellow"
    if dl >= 30: return "grey"
    return "red"


def calc_buyout_rate(sales: list[dict], orders: list[dict]) -> float:
    """Выкупаемость за период: продажи / заказы (кроме isCancel)."""
    total_orders = sum(1 for o in orders if not o.get("isCancel"))
    total_sales = len(sales)
    if total_orders == 0:
        return 0.22  # fallback
    return round(total_sales / total_orders, 4)


def calc_daily_velocity(orders: list[dict], days: int) -> float:
    """Средняя скорость заказов в день (без отмен)."""
    real_orders = [o for o in orders if not o.get("isCancel")]
    return len(real_orders) / max(days, 1)
