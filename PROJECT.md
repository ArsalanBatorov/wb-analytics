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
- Frontend: React, TypeScript, Vite, Recharts
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
- logistics_calc.py — калькулятор логистики и маржи
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
- products (~40) — товары: nm_id, volume_liters, dimensions, cost_price, warehouse_name, avg_price_api
- realization_records (9555) — строки отчёта: rrd_id, nm_id, doc_type, retail_price, delivery_rub, ppvz_for_pay
- realization_daily_stats (750) — агрегация по дням
- product_daily_stats — дневная стата: заказы, выкупы, расходы
- warehouse_tariffs (45) — тарифы складов: FL, EL (уже с коэф склада)
- campaigns, bid_logs, clusters, cluster_daily_stats
- stock_snapshots, product_plans, schedules, app_settings

### Особенности realization_records
- doc_type: Продажа / Возврат / пустое (= логистика)
- Логистические строки идут ПАРАМИ: прямая (>150р) + обратная (<150р)
- НЕТ колонки склад — ограничение WB API
- delivery_rub у строк Продажа/Возврат = 0

## 4. ФОРМУЛЫ

### 4.1 Прямая логистика (подтверждено 01.05.2026, 11/16 строк ±2р)
Прямая = (FL_склада + EL_склада * (vol - 1)) * ИЛ + цена * ИРП%
- FL, EL из warehouse_tariffs (уже включают коэф склада)
- ИЛ = индекс локализации (сейчас 1.07)
- ИРП = индекс распределения продаж (сейчас 1.74%)

### 4.2 Обратная логистика (НЕ УСТАНОВЛЕНА)
- Зависит от склада, не фиксированная
- В коде: фикс 143р — НЕВЕРНО
- WB заявил 50+14*(vol-1) с 20.03.2026, но факт не совпадает

### 4.3 Параметры
- seller_coef: 0.645 (WB удерживает ~35.5%)
- Комиссия кВВ: ~29.5% (Одежда FBO), -5% за 5+ опций
- Эквайринг: ~1%
- logistics_multiplier: 1.85 — КОСТЫЛЬ, убрать

### 4.4 Индексы (история)
27.04: ИЛ=1.07 ИРП=1.74%
20.04: ИЛ=1.07 ИРП=1.77%
13.04: ИЛ=1.07 ИРП=1.77%
06.04: ИЛ=1.07 ИРП=1.76%
30.03: ИЛ=1.08 ИРП=1.82%
23.03: ИЛ=1.07 ИРП=1.80%

### 4.5 Таблица КТР/КРП по доле локализации
95-100%: КТР=0.50 КРП=0%
70-74.99%: КТР=1.00 КРП=0%
55-59.99%: КТР=1.05 КРП=2.00%
45-49.99%: КТР=1.20 КРП=2.05%
30-34.99%: КТР=1.50 КРП=2.15%
10-14.99%: КТР=1.75 КРП=2.35%
0-4.99%: КТР=2.00 КРП=2.50%

## 5. ТОВАРЫ

- 123877379 DARKBEIGE: Костюм деловой, 7.875л (35x5x45), цена ~10500-11079
- 176060304 BIEGESINGLE: Костюм брючный, 1.125л (5x5x45), цена ~10369
- 46544844 WHITE: Костюм праздничный, 7.875л (35x5x45), цена ~11317
- Категория: Костюмы (177), бренд Refulgence-Balgini, FBO

## 6. ПЛАН

### P0 — критично
1. Прямая логистика по складам — DONE 01.05
2. calc_delivery: ИЛ * вся база — DONE 01.05
3. Убрать logistics_multiplier=1.85 — TODO
4. Обратная логистика: установить формулу — TODO
5. Колонка склад в realization_records — TODO

### P1 — важно
6. Двойной эквайринг (продажа + возврат) — TODO
7. Исторические ИЛ/ИРП по неделям — TODO
8. Дефолтная сортировка по заказам — TODO
9. Дровер с 4 графиками + сводка — DONE
10. Интеграция комиссий, seller_coef=0.645 — DONE
11. Скидка -5% за 5+ опций — DONE

### P2 — улучшения
12. Автообновление ИЛ/ИРП из WB API — TODO
13. Алерты при смене тарифов — TODO
14. Сверка факт vs прогноз — TODO
15. Экспорт отчётов — TODO

## 7. CHANGELOG
- 01.05.2026: исправлен calc_delivery_per_shipment (ИЛ * вся база)
- 01.05.2026: подтверждена формула прямой логистики (11/16 ±2р)
- 01.05.2026: обнаружено: FL/EL в warehouse_tariffs уже с коэф склада
- 01.05.2026: обнаружено: обратная логистика зависит от склада
- 01.05.2026: создан PROJECT.md
- 28.04.2026: обновлены warehouse_tariffs (45 складов)
- 26.04.2026: добавлены продукты в БД
- 15.04.2026: initial migration + app_settings

## 8. БЫСТРЫЕ КОМАНДЫ
cd /root/wb-analytics/backend && source /root/wb-analytics/venv/bin/activate
systemctl restart wb-backend wb-celery wb-celery-beat
journalctl -u wb-backend -f
journalctl -u wb-celery -f
