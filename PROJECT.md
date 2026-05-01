# WB-ANALYTICS — Project Bible
> Последнее обновление: 2026-05-01

## 1. ИНФРАСТРУКТУРА

### Сервер
- Путь: /root/wb-analytics/
- Venv: /root/wb-analytics/venv/
- Backend: /root/wb-analytics/backend/
- Frontend: /root/wb-analytics/frontend/
- Frontend build (раздаёт nginx): /var/www/wb-bidder/

### Сервисы (systemd)
- wb-backend: uvicorn app.main:app на 127.0.0.1:8100
- wb-celery: celery worker (concurrency=1)
- wb-celery-beat: celery beat

### Рестарт
systemctl restart wb-backend wb-celery wb-celery-beat

### Стек
- Backend: Python 3.12, FastAPI, SQLAlchemy (async), Celery + Redis
- Frontend: React 19, TypeScript, Vite 8, Recharts 3, Ant Design 6, axios, dayjs
- DB: PostgreSQL wb_bidder
- Очередь: Redis localhost:6379/1
- Nginx: порт 80, /api/ → uvicorn:8100, / → /var/www/wb-bidder

## 2. СТРУКТУРА КОДА

### Backend API (backend/app/api/)
- analytics.py — старые financial-* endpoints (используются Dashboard)
- margin.py — НОВЫЙ: /margin/{summary,daily,products} (фактическая маржа)
- settings.py, sync.py, dashboard.py, campaigns.py, clusters.py,
  minus_queue.py, schedule.py, stats.py

### Backend Services (backend/app/services/)
- margin_fact.py — НОВЫЙ: расчёт фактической маржи кассовым методом
- logistics_calc.py — модельный расчёт (logistics_multiplier=1.85, MODEL only)
- data_sync.py — синхронизация с WB API (включая sync_realization_daily)
- stats_collector.py, bidder.py, wb_api/

### Backend Scripts (backend/scripts/)
- check_data.py, check_gaps.py, check_rds.py, check_rds_gaps.py
- test_margin.py — тесты margin_fact

### Frontend Pages (frontend/src/pages/)
- Margin.tsx — НОВАЯ, единственная активная страница (KPI, график, таблица SKU)
- Dashboard.tsx, Settings.tsx, Products.tsx, Campaigns.tsx, Campaign.tsx,
  ProductDetail.tsx — ВРЕМЕННО ОТКЛЮЧЕНЫ (импортируют отсутствующие функции
  из client.ts: updateSettings, fetchCampaigns, syncCampaigns, startCampaign,
  pauseCampaign, updateCampaign, fetchProductDrawer)

### Frontend API (frontend/src/api/client.ts)
- Period helpers: makePeriod, makeCustomPeriod
- Old model: fetchSummary, fetchProducts, fetchProductDaily, fetchPlanStatus
- Financial: fetchFinancial{Summary,Daily,Products,ProductDaily}
- Margin (NEW): fetchMargin{Summary,Daily,Products} + типы
- Settings: fetchSettings, updateGlobalSettings, updateCostPrice, updatePlan
- Sync: syncAll, syncProducts, syncAds
- Advertising: fetchAdvertising{Summary,Products,Daily}

## 3. БАЗА ДАННЫХ

### Таблицы
- products (~40 строк): nm_id, vendor_code, cost_price, dimensions,
  warehouse_name, avg_price_api
- realization_records (~9555 строк): rrd_id, nm_id, doc_type, sale_dt, order_dt,
  retail_price, ppvz_for_pay, delivery_rub, acquiring_fee, storage_fee, penalty,
  quantity, subject_name, barcode. БЕЗ warehouse_name (восстанавливается из
  stock_snapshots на дату).
- realization_daily_stats (~750 строк, 16.03→26.04, 50 nm_id): агрегированные
  данные финотчёта WB по дням × nm_id. ИСТОЧНИК ДЛЯ ФАКТА.
  Поля: stat_date, nm_id, sales_count, sales_revenue, returns_count,
  returns_revenue, payout_sales, payout_returns, logistics_cost,
  rebill_logistics_cost, storage_cost, acceptance_cost, deduction_cost,
  penalty_cost, additional_payment, acquiring_sales, acquiring_returns,
  commission_sales, commission_returns, net_payout, net_qty,
  cost_price_estimate, profit_estimate
- product_daily_stats: модельные дневные метрики (orders, buyouts, ad_spend, …)
- warehouse_tariffs (45 складов): warehouse_name, first_liter_rate,
  extra_liter_rate (УЖЕ С КОЭФФИЦИЕНТОМ СКЛАДА)
- product_plans: nm_id, month, plan_orders (требует расширения для plan_margin)
- app_settings: ktr=1.07, irp=1.77, seller_coef=0.647, tax_rate=1.0,
  vat_rate=5.0, wb_api_token

## 4. ФИНАНСОВАЯ МОДЕЛЬ

Два независимых контура. Не смешивать.

### 4.1 ФАКТ (cash-method) — источник истины
- Файл: app/services/margin_fact.py
- API: GET /margin/{summary,daily,products}
- UI: страница Margin.tsx
- Источник: realization_daily_stats (тот же отчёт, что финотчёт WB)
- Период: ежедневно
- Формула:
  margin = net_payout − cogs − ad_spend
  где:
    net_payout уже включает все удержания WB (логистика, корр.ВВ,
                хранение, штрафы), комиссию и эквайринг
    cogs       = cost_price_estimate из realization_daily_stats
    ad_spend   = SUM(product_daily_stats.ad_spend) за период

### 4.2 МОДЕЛЬ (forecast) — для прогноза текущего дня
- Файл: app/services/logistics_calc.py
- Используется только Dashboard и старые financial-* endpoints
- Содержит logistics_multiplier=1.85 (УБРАТЬ когда обратная логистика
  будет правильной)
- Прямая логистика: (FL + EL*(vol−1))*KTR + price*IRP/100
- Обратная логистика: hardcoded 143 ₽ (НЕВЕРНО, нужно 50 + 14*(vol−1))

### 4.3 Сверка с финотчётом WB (16.03−26.04, 42 дня)
- Δ К перечислению = 0 ₽ для 5 недель из 6
- Δ Логистика = 3-10% (расхождение «Доставка» vs «Доставка по выкупам»)
- Δ Корр. ВВ = 0 ₽
- Итог: маржа −178 697 ₽ (−2.95%) на выручку 6 047 999 ₽

## 5. ТЕКУЩЕЕ СОСТОЯНИЕ UI

### 5.1 Активная страница: Margin.tsx
- Селектор периода: пресеты 7/14/30 дней + текущий месяц + custom RangePicker
- 6 KPI-карточек: Выручка, Маржа ₽, Маржа %, COGS, Логистика, Реклама
- 4 доп.карточки: К перечислению, Хранение, Корр.ВВ, Возвраты шт
- График: BarChart по дням (Recharts)
- Таблица SKU: nm_id, Продажи, Возвраты, Выручка, COGS, Логистика, Реклама,
  Маржа ₽ (зелёный/красный), Маржа % (Tag по диапазонам)
- Сортировка по марже asc по умолчанию (худшие сверху)
- Клик по nm_id открывает карточку на Wildberries

### 5.2 Известные баги (TODO)
- График: вложенный <Bar> внутри <Bar> вместо <Cell> — все столбцы одного
  цвета, tooltip показывает значение N раз
- nm_id=0 в таблице — общие удержания WB не привязаны к SKU
- Settings.tsx, Dashboard.tsx, Products.tsx, Campaigns.tsx — отключены,
  т.к. импортируют отсутствующие функции из client.ts

### 5.3 Backend API margin (тестовые запросы)
GET /margin/summary?date_from=2026-04-13&date_to=2026-04-19
GET /margin/daily?date_from=2026-04-13&date_to=2026-04-19
GET /margin/products?date_from=2026-04-13&date_to=2026-04-19

## 6. ПЛАН РАБОТ

### P0 (закончить интерфейс, основная фича)
1. Починить график: заменить вложенный <Bar> на <Cell> (зелёный/красный)
2. Восстановить Settings.tsx (добавить updateSettings в client.ts)
3. Восстановить Dashboard.tsx (добавить fetchProductDrawer в client.ts)
4. Расширить product_plans: plan_margin, plan_revenue, plan_orders
5. CRUD UI для plan_margin (страница «Планы»)
6. Страница «План vs Факт»: cumulative chart, Δ к плану по SKU

### P1 (доработка)
- Восстановить Products.tsx + Campaigns.tsx
- CSV-export таблиц
- Loading skeletons + empty states
- React Query / SWR кэширование
- Цветовые статус-теги по правилам (margin_pct < 0 → красный, < 5 → жёлтый…)

### P2 (улучшения)
- Убрать logistics_multiplier=1.85, поправить обратную логистику (50+14*(vol−1))
- Восстановить warehouse в realization_records через stock_snapshots
- Алерты: маржа < 0, возвраты > X%, склад < N дней, спайки рекламы
- Глоссарий терминов в UI

## 7. БЫСТРЫЕ КОМАНДЫ

# Активация окружения
cd /root/wb-analytics/backend && source /root/wb-analytics/venv/bin/activate

# Рестарт сервисов
systemctl restart wb-backend wb-celery wb-celery-beat

# Логи
journalctl -u wb-backend -f
journalctl -u wb-celery -f

# Тест фактической маржи
cd /root/wb-analytics/backend && python scripts/test_margin.py

# Билд + публикация фронта
cd /root/wb-analytics/frontend && npm run build && \
  rm -rf /var/www/wb-bidder/assets /var/www/wb-bidder/index.html && \
  cp -r dist/* /var/www/wb-bidder/

# Синхронизация финотчёта WB
curl -X POST "http://127.0.0.1:8100/sync/realization?date_from=2026-04-01&date_to=2026-05-01"

# Просмотр PROJECT.md
cat /root/wb-analytics/PROJECT.md

## 8. CHANGELOG

### 01.05.2026 (вечер)
- UI: страница Margin.tsx работает в продакшене на /var/www/wb-bidder/
- API: /margin/{summary,daily,products} рабочие, под реальные сигнатуры margin_fact
- frontend/src/api/client.ts: добавлены fetchMargin* + типы
- App.tsx: упрощён до одного компонента <Margin/> (остальные страницы
  отключены до восстановления отсутствующих функций client.ts)
- Проверено в браузере: за 30 дней (02.04-01.05) маржа -227 840 ₽ (-6.8%)
  на выручку 3 309 246 ₽

### 01.05.2026 (день)
- backend/app/services/margin_fact.py: расчёт маржи из realization_daily_stats
- Сверка с финотчётом WB: Δ=0 для 5 из 6 недель
- backend/scripts/: test_margin, check_data, check_gaps, check_rds, check_rds_gaps
- .gitignore: venv, node_modules, celerybeat, .env, .bak
- Удалён из tracking backend/celerybeat-schedule

### 01.05.2026 (утро)
- Подтверждена формула прямой логистики (11/16 ±2 ₽)
- Обнаружено: FL/EL в warehouse_tariffs уже с коэф склада
- Обнаружено: обратная логистика зависит от склада

### 28.04.2026
- Обновлены warehouse_tariffs (45 складов)

### 26.04.2026
- Добавлены продукты в БД

### 15.04.2026
- Initial migration + app_settings
