# WB-ANALYTICS — Project Bible
> Последнее обновление: 2026-05-01

## 1. ИНФРАСТРУКТУРА

### Сервер
- Путь: /root/wb-analytics/
- Venv: /root/wb-analytics/venv/
- Backend рабочая директория: /root/wb-analytics/backend/
- Frontend build: /var/www/wb-analytics/

### Сервисы (systemd)
- wb-backend: uvicorn app.main:app на 127.0.0.1:8100
- wb-celery: celery worker (concurrency=1)
- wb-celery-beat: celery beat

### Рестарт
systemctl restart wb-backend wb-celery wb-celery-beat

### Стек
- Backend: Python 3.12, FastAPI, SQLAlchemy (async), Celery + Redis
- Frontend: React, TypeScript, Vite, Recharts, Ant Design
- DB: PostgreSQL wb_bidder
- Очередь: Redis localhost:6379/1
- Nginx: порт 80, /api/ -> uvicorn:8100, / -> static

## 2. СТРУКТУРА КОДА

### Backend API (backend/app/api/)
- dashboard.py — главная панель
- analytics.py — аналитика
- campaigns.py — рекламные кампании
- clusters.py — кластеры ключевых слов
- stats.py — статистика продуктов
- sync.py — синхронизация с WB API
- settings.py — настройки
- schedule.py — расписания биддера
- minus_queue.py — минус-слова

### Backend Services (backend/app/services/)
- logistics_calc.py — калькулятор логистики и маржи (МОДЕЛЬ)
- margin_fact.py — расчёт фактической маржи (ФАКТ, кассовый метод) — НОВОЕ
- bidder.py — логика автоставок
- data_sync.py — синхронизация данных с WB
- stats_collector.py — сбор статистики
- auto_minus.py — автоматические минус-слова
- scheduler.py — планировщик задач
- wb_api/client.py — HTTP-клиент WB API
- wb_api/rate_limiter.py — ограничение запросов
- wb_api/token_loader.py — загрузка токенов

### Backend Tasks Celery (backend/app/tasks/)
- bidding.py, statistics.py, minus.py, frequency.py, scheduling.py

### Frontend (frontend/src/pages/)
- Dashboard.tsx, Products.tsx, ProductDetail.tsx
- Campaigns.tsx, Campaign.tsx, Settings.tsx

## 3. БАЗА ДАННЫХ

### Таблицы
- products (~40) — товары: nm_id, volume_liters, dimensions, cost_price, warehouse_name
- realization_records (9555) — строки отчёта: rrd_id, nm_id, doc_type, ppvz_for_pay, delivery_rub, sale_dt, order_dt, acquiring_fee, storage_fee, penalty, quantity
- product_daily_stats — дневная стата: заказы, выкупы, расходы, реклама, маржа (модель)
- warehouse_tariffs (45) — тарифы складов: first_liter_rate, extra_liter_rate (уже с коэф склада)
- product_plans — планы по nm_id × month (текущая структура: только plan_orders)
- campaigns, bid_logs, clusters, cluster_daily_stats
- stock_snapshots, schedules, app_settings

### Особенности realization_records
- doc_type: Продажа / Возврат / пустое (= логистика)
- Логистические строки идут ПАРАМИ: прямая (>150р) + обратная (<150р)
- Дата операции: sale_dt (дата движения денег); order_dt — дата исходного заказа
- НЕТ колонки склад — ограничение WB API
- delivery_rub у строк Продажа/Возврат = 0
- ppvz_for_pay по продажам уже net после комиссии WB и эквайринга
- acquiring_fee при возвратах — отдельное удержание (вычитать дополнительно)

### app_settings (актуальные значения)
- ktr=1.07, irp=1.77, seller_coef=0.647, tax_rate=1.0, vat_rate=5.0

## 4. ФИНАНСОВАЯ МОДЕЛЬ — ДВА КОНТУРА

Система оперирует двумя независимыми финансовыми контурами.
Они НЕ должны смешиваться в одном UI-блоке.

### 4.A. Контур ФАКТ (кассовый, ежедневный)
- Назначение: оперативное управление, сверка с планом
- Источник: realization_records (отчёт WB)
- Метод: кассовый по дате операции (sale_dt)
- Периодичность: каждый день
- Реализация: app/services/margin_fact.py
- НЕ предназначен для оценки юнит-экономики отдельных заказов

### 4.B. Контур МОДЕЛЬ (прогнозная, для свежих дней)
- Назначение: прогноз маржи на сегодня/вчера, когда отчёт ещё не пришёл
- Источник: product_daily_stats (заказы/выкупы) + формулы логистики
- Метод: модельный по формулам
- Реализация: app/services/logistics_calc.py
- Точность ограничена точностью формул (см. раздел 5)

### 4.C. Сверка
Раз в неделю (после прихода отчёта WB) автоматически сверять:
- Маржу из ФАКТА (кассовый, по сумме за неделю)
- Маржу из МОДЕЛИ (прогнозную, та же неделя)
- Расхождение по статьям → индикатор точности формул

## 5. ФОРМУЛЫ

### 5.1 Прямая логистика — МОДЕЛЬ (подтверждено 01.05.2026, 11/16 строк ±2р)
Прямая = (FL_склада + EL_склада * (vol - 1)) * ИЛ + цена * ИРП%
- FL, EL из warehouse_tariffs (уже включают коэф склада)
- ИЛ = индекс локализации (сейчас 1.07)
- ИРП = индекс распределения продаж (сейчас 1.77%)

### 5.2 Обратная логистика — МОДЕЛЬ (НЕ УСТАНОВЛЕНА)
- Зависит от склада, не фиксированная
- В коде: фикс 143р — НЕВЕРНО
- WB заявил 50+14*(vol-1) с 20.03.2026, но факт не совпадает
- TODO: измерить расхождение по конкретным складам

### 5.3 Маржа ФАКТ (кассовый метод) — основная формула
margin(D, nm_id) =
    payout_sales (Σ ppvz_for_pay по Продажам дня D)
  − payout_returns (Σ ppvz_for_pay по Возвратам дня D)
  − acquiring_returns (Σ acquiring_fee по Возвратам дня D)
  − logistics (Σ delivery_rub за день D)
  − storage (Σ storage_fee за день D)
  − penalty (Σ penalty за день D)
  − cogs ((qty_sold − qty_returned) × cost_price)
  − ad_spend (из product_daily_stats за день D)

ВАЖНО: комиссия WB и эквайринг по ПРОДАЖАМ отдельно НЕ вычитаются —
они уже учтены в ppvz_for_pay. Иначе будет двойной счёт.

### 5.4 Параметры (из app_settings)
- seller_coef: 0.647 (WB удерживает ~35.3%)
- Комиссия кВВ: ~29.5% (Одежда FBO, предмет 177), -5% за 5+ опций
- Эквайринг: ~1%
- ИЛ (ktr): 1.07
- ИРП (irp): 1.77%
- logistics_multiplier: 1.85 — КОСТЫЛЬ, убрать после фиксации обратной

### 5.5 Индексы (история)
27.04: ИЛ=1.07 ИРП=1.77%
20.04: ИЛ=1.07 ИРП=1.77%
13.04: ИЛ=1.07 ИРП=1.77%
06.04: ИЛ=1.07 ИРП=1.76%
30.03: ИЛ=1.08 ИРП=1.82%
23.03: ИЛ=1.07 ИРП=1.80%

### 5.6 Таблица КТР/КРП по доле локализации
95-100%: КТР=0.50 КРП=0%
70-74.99%: КТР=1.00 КРП=0%
55-59.99%: КТР=1.05 КРП=2.00%
45-49.99%: КТР=1.20 КРП=2.05%
30-34.99%: КТР=1.50 КРП=2.15%
10-14.99%: КТР=1.75 КРП=2.35%
0-4.99%: КТР=2.00 КРП=2.50%

## 6. ТОВАРЫ
- 123877379 DARKBEIGE: Костюм деловой, 7.875л (35x5x45), цена ~10500-11079
- 176060304 BIEGESINGLE: Костюм брючный, 1.125л (5x5x45), цена ~10369
- 46544844 WHITE: Костюм праздничный, 7.875л (35x5x45), цена ~11317
- Категория: Костюмы (177), бренд Refulgence-Balgini, FBO

## 7. ПЛАН РАБОТ

### P0 — фундамент данных (блокирует всё остальное)
1. Прямая логистика по складам — DONE 01.05
2. calc_delivery: ИЛ * вся база — DONE 01.05
3. Сервис фактической маржи (margin_fact.py) — IN PROGRESS 01.05
4. Обратная логистика: установить формулу — TODO
5. Убрать logistics_multiplier=1.85 — TODO (после п.4)
6. Колонка склад в realization_records (или восстановление через stock_snapshots) — TODO

### P1 — план и сверка (новое направление)
7. Расширить product_plans (добавить plan_revenue, plan_margin, plan_ad_spend) — TODO
8. Автогенерация плана из истории — TODO
9. UI: ввод/редактирование плана — TODO
10. UI: экран «План vs Факт по марже» (главный операционный экран) — TODO
11. UI: единый PeriodFilter с date_from/date_to и пресетами — TODO
12. Расширение client.ts под новые financial-* endpoint'ы — TODO

### P2 — P&L и доводка
13. UI: экран P&L (отчёт WB как есть, с drill-down) — TODO
14. Сверка ФАКТ vs МОДЕЛЬ за неделю — TODO
15. Двойной эквайринг (продажа + возврат) — учтено в margin_fact.py 01.05
16. Исторические ИЛ/ИРП по неделям — TODO
17. Дефолтная сортировка по заказам — TODO
18. Дровер с 4 графиками + сводка — DONE
19. Интеграция комиссий, seller_coef=0.647 — DONE
20. Скидка -5% за 5+ опций — DONE

### P3 — улучшения
21. Автообновление ИЛ/ИРП из WB API — TODO
22. Алерты при смене тарифов — TODO
23. Экспорт отчётов CSV — TODO
24. Часовой пояс МСК явно везде — TODO

## 8. ГЛОССАРИЙ

- **ФАКТ (маржа)** — кассовая маржа за день, посчитанная по realization_records.
  Не предназначена для юнит-экономики отдельных заказов.
- **МОДЕЛЬ (маржа)** — прогнозная маржа по формулам, для свежих дней без отчёта.
- **P&L** — берётся из недельного отчёта WB как есть, не считается формулами.
- **Net payout** — поле ppvz_for_pay в realization_records, сумма к выплате
  после удержаний WB.
- **Выручка (revenue_net)** — sum(ppvz_for_pay) по строкам doc_type='Продажа'.
- **COGS** — себестоимость проданных = (qty_sold − qty_returned) × cost_price.
- **План** — задаётся по nm_id × месяц; ключевая метрика плана — маржа
  (с производными: orders, revenue).
- **Кассовый метод** — каждая операция учитывается в дне sale_dt, без матчинга
  заказ→выкуп→возврат.

## 9. CHANGELOG

- 01.05.2026: создан app/services/margin_fact.py (фактическая маржа, кассовый метод)
- 01.05.2026: разделены два контура: ФАКТ (кассовый) и МОДЕЛЬ (формулы)
- 01.05.2026: P&L переопределён как «отчёт WB как есть», без расчёта формулами
- 01.05.2026: исправлен calc_delivery_per_shipment (ИЛ * вся база)
- 01.05.2026: подтверждена формула прямой логистики (11/16 ±2р)
- 01.05.2026: обнаружено: FL/EL в warehouse_tariffs уже с коэф склада
- 01.05.2026: обнаружено: обратная логистика зависит от склада
- 01.05.2026: создан PROJECT.md
- 28.04.2026: обновлены warehouse_tariffs (45 складов)
- 26.04.2026: добавлены продукты в БД
- 15.04.2026: initial migration + app_settings

## 10. БЫСТРЫЕ КОМАНДЫ

cd /root/wb-analytics/backend && source /root/wb-analytics/venv/bin/activate
systemctl restart wb-backend wb-celery wb-celery-beat
journalctl -u wb-backend -f
journalctl -u wb-celery -f

# Тест фактической маржи
cd /root/wb-analytics/backend && python test_margin.py

# Просмотр PROJECT.md
cat /root/wb-analytics/PROJECT.md
