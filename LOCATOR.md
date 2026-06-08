# Locator — контроль локализации и остатков BALGINI
# Дата: 2026-06-08 | ИЛ: 1.10 | ИРП: 1.60% | Цель: ИЛ<1.0, ИРП<0.1%

## Правило обрыва ИРП
ДЛ 55-59% -> КРП 2% (растёт)
ДЛ >= 60% -> КРП 0% (не растёт)
Стратегия: пробить 60% по топ-SKU, удержать.

## Таблица КТР/КРП
ДЛ 95-100: КТР 0.50, КРП 0.00
ДЛ 60-94: КТР 0.60-1.00, КРП 0.00
ДЛ 55-59: КТР 1.05, КРП 2.00 (критическая зона!)
ДЛ 50-54: КТР 1.10, КРП 2.05
ДЛ 0-49: КТР 1.20-2.00, КРП 2.05-2.50

## Константы бренда
Выкупаемость 22%, оборачиваемость 30дн (45 с буфером), страховой x1.3
Сезонность июня x2 (просадка), коробка 20 костюмов, ~80 заказов/день

## Регионы и ДЛ
Центр: 33% заказов, ДЛ 83% (цель 85%+)
Юг: 17%, ДЛ 60% (цель 70%)
Приволжье: 14%, ДЛ 48% (цель 70-75%)
ДВ/Сибирь: 12%
СЗ: 10.5%, ДЛ 7-13% (цель 55-60%)
Урал: 8%, ДЛ 43% (цель 65-70%)

## Quick wins (SKU с ДЛ 50-59%)
DARKBEIGE 48: ~50 зак/мес, ДЛ 44% -> 60%, -0.5 п.п. ИРП
WHITE 50: ~45 зак/мес, ДЛ 57% -> 65%, -0.4 п.п. ИРП
DARKBEIGE 50: ~40 зак/мес, ДЛ 44% -> 60%, -0.4 п.п. ИРП
DARKBEIGE 46: ~30 зак/мес, ДЛ 50% -> 60%, -0.3 п.п. ИРП
WHITE 52: ~30 зак/мес, ДЛ 60% -> 67%, -0.2 п.п. ИРП

## Структура backend
app/api/locator.py — роутер
app/services/locator/__init__.py
app/services/locator/locator_config.py — константы, баркоды
app/services/locator/locator_calc.py — ДЛ, ИРП, ИЛ, OOS
app/services/locator/locator_stocks.py — WB API остатки
app/services/locator/locator_packing.py — генератор упаковки
app/services/locator/locator_recommend.py — рекомендации поставок
app/models/locator.py — модели БД
app/tasks/locator_tasks.py — Celery задачи

## Структура frontend
pages/LocatorDashboard.tsx — дашборд
components/locator/LocatorKPI.tsx — KPI блок
components/locator/LocatorTrafficLight.tsx — светофор
components/locator/LocatorStockTable.tsx — таблица остатков
components/locator/LocatorDLChart.tsx — график ДЛ
components/locator/LocatorIRPChart.tsx — график ИРП/ИЛ
components/locator/LocatorQuickWins.tsx — приоритетные SKU
components/locator/LocatorPackingPlan.tsx — план упаковки
components/locator/LocatorRecommendations.tsx — рекомендации
components/locator/LocatorAlerts.tsx — алёрты

## API эндпоинты
GET /api/locator/summary — сводка ИЛ/ИРП/ДЛ
GET /api/locator/stocks — остатки WB (фильтр: склад, SKU, размер)
GET /api/locator/dl — ДЛ по артикулам с КТР/КРП
GET /api/locator/irp-history — история ИРП/ИЛ
GET /api/locator/quick-wins — приоритетные SKU для пробития
GET /api/locator/velocity — скорость заказов 30дн
GET /api/locator/factory — остатки фабрики
GET /api/locator/recommendations — рекомендации поставок
GET /api/locator/packing — план упаковки
POST /api/locator/packing/generate — сгенерировать упаковку
GET /api/locator/alerts — активные алёрты
POST /api/locator/sync — ручной запуск синхронизации

## Модели БД
locator_stocks — остатки WB (sku, размер, склад, кол-во, дата)
locator_order_velocity — скорость заказов (sku, размер, регион, кол-во)
locator_dl — ДЛ по артикулам (sku, размер, ДЛ%, КТР, КРП, дата)
locator_irp_history — история ИРП/ИЛ (дата, ИЛ, ИРП)
locator_factory_stock — остатки фабрики (sku, размер, кол-во)
locator_shipments — поставки (волна, коробка, регион, состав, статус)
locator_packing_boxes — коробки (номер, баркоды, регион, статус)

## Алгоритм рекомендаций
1. Для SKU x размер x регион: дней до OOS = остаток / (расход_30дн / 30)
2. Приоритет: P0(ДЛ 55-59%) > P1(крит. 0) > P2(OOS<14дн) > P3(поддержка >60%)
3. Группировка в коробки по 20 шт
4. Очерёдность отправки: СЗ -> Приволжье -> Урал -> Юг -> Центр

## Светофор
Красный: ДЛ < 30% (не трогать)
Жёлтый: ДЛ 50-59% (quick win, ПРИОРИТЕТ)
Зелёный: ДЛ >= 60% (поддерживать)
Серый: ДЛ 30-49% (средний приоритет)

## Алёрты
HIGH: критический 0 на складе
HIGH: ДЛ вошёл в зону 55-59%
HIGH: ДЛ упал ниже 60%
HIGH: OOS < 7 дней
MEDIUM: перетарка > 20 шт
MEDIUM: ИРП вырос > 0.1 п.п. за неделю

## План реализации (6-7 часов)
1. Миграция БД (30 мин)
2. locator_config.py (20 мин)
3. locator_stocks.py (40 мин)
4. locator_calc.py (40 мин)
5. locator_recommend.py (30 мин)
6. locator_packing.py (30 мин)
7. api/locator.py (40 мин)
8. Celery задачи (20 мин)
9. Frontend дашборд (2-3 ч)
10. Интеграция в main.py + App.tsx (10 мин)
