# WB-Analytics — статус проекта

**Обновлено:** 2026-05-05
**Сервер:** /root/wb-analytics/, IP 154.83.149.167
**GitHub:** https://github.com/ArsalanBatorov/wb-analytics (branch main)

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy async, Celery + Redis, systemd `wb-backend` на 127.0.0.1:8100
- Frontend: React 19, TypeScript, Vite 8, Ant Design 6, Recharts 3
- DB: PostgreSQL wb_bidder, пользователь bidder
- Web: nginx, статика /var/www/wb-bidder/
- venv: /root/wb-analytics/venv/

## Архитектура данных

Два источника правды по марже:

1. Расчётная маржа — таблица product_daily_stats. Заполняется Celery-таском из WB API (заказы, реклама). Поля: order_count, order_sum, buyout_count, buyout_sum, ad_spend, ad_views, ad_clicks, ad_orders, margin_profit, margin_clean, delivery_cost, return_cost, storage_cost, commission_amount, cost_price_total. Задержка 1-2 дня. Источник для оперативки и плана vs факт.

2. Фактическая маржа из финотчёта — realization_daily_stats. Из еженедельного финансового отчёта WB. Реальные деньги к перечислению, удержания, штрафы, корректировки. Задержка 7-14 дней. Источник для бухгалтерии и сверки.

## Страницы frontend

Активные:
- План/Факт (Margin.tsx) — будет переименована в меню в «Фин. отчёт». Источник realization_daily_stats. KPI: выручка, маржа ₽, маржа %, себестоимость, логистика, реклама. Таблица SKU с vendor_code, nm_id, title.
- Реклама (Advertising.tsx) — KPI (расход, ДРР, показы, клики, CTR, CPC, CPO) + таблица SKU с сортировками.
- Настройки (Settings.tsx) — налоги (tax_rate, vat_rate, seller_coef), индексы WB (ИЛ, ИРП) с tooltip и тегами свежести.

Отключённые (импорты несуществующих функций ломают билд): Dashboard, Products, Campaigns, Campaign, ProductDetail.

## Backend API

Margin (/margin/*):
- GET /margin/summary, /margin/daily, /margin/products — все по realization_daily_stats. /margin/products делает JOIN с products (vendor_code, title).

Analytics (/analytics/*):
- /advertising-summary, /advertising-products, /advertising-daily
- /summary, /products, /products/{nm_id}/daily, /financial-*, /plan-status, /product-drawer/{nm_id}

Settings (/settings/*):
- GET /settings/ — все настройки одним JSON
- PUT /settings/global — обновление tax_rate, vat_rate, ktr (ИЛ), irp (ИРП). Без автопересчёта истории.
- PUT /settings/cost-price — себестоимость SKU + пересчёт метрик одного SKU.

## База данных

Ключевые таблицы:
- realization_daily_stats — факт из финотчёта. Период: 2026-03-16 → 2026-05-03 (49 дней, 1205 строк).
- product_daily_stats — расчёт. До 2026-04-30 заполнено (~190-192 SKU/день). За 01-05.05 ещё нет (синк с задержкой).
- products — каталог SKU (nm_id, vendor_code, title, brand, cost_price, размеры, warehouse_coef).
- product_plans — план по SKU на месяц (id, nm_id, month, plan_orders, plan_revenue). Почти пустая, использовать не будем (вести в Google).
- campaigns, cluster_*, bid_log, minus_queue, schedule, settings — рекламная инфраструктура.

## Что сделано в текущей сессии

1. Точка A — график маржи: вложенный Bar заменён на Cell (зелёный/красный по знаку).
2. App.tsx переписан на Ant Design Layout с боковым меню. Подключены Margin, Advertising, Settings.
3. Margin.tsx: добавлена кнопка «Вчера», колонка «Артикул продавца» (vendor_code), nm_id как ссылка на WB, COGS → Себестоимость, заголовок «План/Факт».
4. Backend margin_fact.py и api/margin.py: LEFT JOIN с products, в ответе vendor_code и title.
5. Settings.tsx: переписан на Card-вёрстку, две секции (Налоги, Индексы WB), tooltip с формулой, теги свежести (если ИЛ/ИРП старше 7 дней — красный тег), баннер StaleSettingsBanner в App.tsx.
6. Settings backend: исправлена ошибка 500 при сохранении (KeyError profit_per_order). Автопересчёт исторических метрик закомментирован — сохранение мгновенное (HTTP 200, ~19 ms).
7. Реклама: создана страница Advertising.tsx с KPI и сортируемой таблицей SKU.

## Известные баги и долги

- За 01-05.05.2026 нет данных в product_daily_stats — нормальная задержка синка WB (1-2 дня).
- Frontend bundle 1.5 MB без code-splitting (warning Vite). Не критично.
- В /margin/products запись с nm_id=0 (общие удержания WB: storage 45 006 ₽, deduction 201 745 ₽) — оставлено как есть.
- Логистический коэффициент 1.85 ещё в коде в нескольких местах — заменить на динамический ИЛ (отложено).
- Warehouse в realization_records не восстановлен.
- Алертов (маржа<0, возвраты>X%, склад<N дн) нет.

## Решения по архитектуре «План/Факт» (следующая итерация)

Меню после итерации: План/Факт | Реклама | Фин. отчёт | Настройки.

- План/Факт — новая страница на месте текущей Margin. Источник product_daily_stats (расчётная маржа).
- Фин. отчёт — это текущая Margin.tsx, переименование только в меню. Файл и логика без изменений.

Состав страницы «План/Факт»:
- Селектор периода (Вчера/7/14/30/Тек.месяц/Свой) и селектор месяца плана.
- Блок «План на месяц» (5 полей, ручной ввод, хранение в БД): план заказы ₽, план выкупы ₽, план заказы шт, план выкупы шт, план валовая прибыль ₽.
- Матрица 5×6: Метрика | План ср/день | Факт ср/день | Прогноз | План общий | Факт общий | % выполнения. Прогноз = факт / пройдено_дней × дней_в_месяце. Цветовые теги: ≥95 зелёный, 80-95 жёлтый, <80 красный. ДРР строкой справочно (без плана), считается из факта ad_spend / order_sum.
- Кумулятивный график с тоггл-переключателем «Выручка / Маржа / Заказы»: план линией, факт кривой, прогноз пунктиром.
- Таблица SKU из product_daily_stats: артикул продавца, nm_id, название, заказы шт/₽, выкупы шт/₽, валовая прибыль, реклама, ДРР%. Без плана по SKU (план ведётся в Google).

Новая таблица БД: monthly_plans (id, month DATE UNIQUE, plan_orders_qty INT, plan_orders_revenue NUMERIC, plan_buyouts_qty INT, plan_buyouts_revenue NUMERIC, plan_margin NUMERIC, created_at, updated_at).

Новые backend-эндпоинты:
- GET /plan-fact/summary?date_from&date_to&month — матрица 5×6
- GET /plan-fact/products?date_from&date_to — таблица SKU из product_daily_stats
- GET /plans/?month=YYYY-MM-01 — текущий план
- PUT /plans/ — сохранение плана месяца

История ИЛ/ИРП (таблица wb_indices_history) — отложена, влияет только на ±1-2% прогнозной маржи.

## План следующей итерации

1. Миграция БД: создать monthly_plans.
2. Backend: роутер /plan-fact/* и /plans/*. Сервис services/plan_fact.py.
3. Frontend: новая страница PlanFact.tsx (матрица + график + таблица SKU + блок ввода плана).
4. Frontend: обновить App.tsx (меню из 4 пунктов).
5. Frontend: добавить функции в client.ts (fetchPlanFactSummary, fetchPlanFactProducts, fetchMonthlyPlan, updateMonthlyPlan).

Оценка: ~2.5-3 ч кода, разбито на 4 блока для последовательного применения через PuTTY.

---

## Сессия 2026-05-05 (вечер) — страница «План/Факт» и фикс таблицы маржи

### A. Фикс таблицы «Маржа по SKU» (Фин. отчёт)
- В `Margin.tsx` пагинация переведена с жёсткого `pageSize: 25` на `defaultPageSize: 25` + `pageSizeOptions: ['25','50','100','200']` — теперь селектор размера страницы реально работает.
- `setProducts(p?.products ?? p?.items ?? (Array.isArray(p) ? p : []))` — добавлен fallback на массив, потому что `fetchMarginProducts` возвращает массив напрямую, а не объект.
- Строка с `nm_id=0` (общие удержания WB) теперь рендерится как «Общие удержания WB» серым курсивом вместо прочерков.
- Бандл: `index-DgYUaV8Q.js`. Коммит `3c4246b` запушен в main.

### B. Новая страница «План/Факт» (расчётная)
**База данных** (Alembic, ревизия `437bceeccdd8`):
- Создана таблица `monthly_plans` (id, month UNIQUE, plan_orders_qty, plan_orders_revenue, plan_buyouts_qty, plan_buyouts_revenue, plan_margin, created_at, updated_at) + индекс `idx_monthly_plans_month`.

**Backend**:
- Модель `app/models/monthly_plan.py` (импорт `from app.database import Base`), экспорт через `app/models/__init__.py`.
- Сервис `app/services/plan_fact.py` (~300 строк): `get_monthly_plan`, `upsert_monthly_plan`, `calc_fact_for_period`, `calc_plan_fact_summary`, `calc_plan_fact_products`. Источник факта — `product_daily_stats` (расчётная маржа, задержка 1-2 дня).
- Роутер `app/api/plan_fact.py`: `GET /plan-fact/summary`, `GET /plan-fact/products`, `GET /plans/`, `PUT /plans/`. Подключено в `main.py` (строки 48, 54-55).
- Pydantic-схема `PlanInput`: `model_config = {"extra": "ignore"}`, поля количества переведены с `int` на `float` (фронт всегда шлёт Number → float). Это закрыло 422-ошибки.
- ДРР считается как `ad_spend / buyouts_revenue * 100` (исправлено с `order_sum` — было нереалистичные 0.5%, стало 4.92% за апрель).

**Frontend**:
- `client.ts`: добавлены `fetchPlanFactSummary`, `fetchPlanFactProducts`, `fetchMonthlyPlan`, `updateMonthlyPlan`.
- Новая страница `pages/PlanFact.tsx` (~280 строк): селектор периода (вчера/7/14/30/текущий месяц/произвольный), селектор «Месяц плана», блок из 5 полей (заказы ₽, выкупы ₽, заказы шт, выкупы шт, валовая прибыль ₽), кнопка «Сохранить план», матрица 6×7 (метрика, план ср/день, факт ср/день, прогноз, план общий, факт общий, % выполнения), SKU-таблица.
- В `InputNumber` всех 5 полей добавлен `parser` — корректно принимает значения вида `14 036 581,67` (пробелы как разделитель тысяч, запятая как десятичная). Без этого Ant Design отбрасывал значения после вставки из Google Sheets.
- `App.tsx`: меню расширено до 4 пунктов — «План/Факт» (новый, расчётный), «Реклама», «Фин. отчёт» (старый Margin.tsx, переименован в меню), «Настройки».
- Подключена русская локаль `dayjs`: `import "dayjs/locale/ru"; dayjs.locale("ru");` + плагин `updateLocale` с массивом названий месяцев с заглавной буквы (Январь, Февраль…). Селектор теперь показывает «Май 2026» вместо «May 2026».

### C. Расписание Celery (для справки)
- `bidding-cycle` — 35 сек (торги).
- `schedule-check` — 60 сек.
- `stats-collection` — 5 мин (рекламная статистика).
- `campaign-sync` — 10 мин.
- `frequency-loader` — 10 мин.
- `daily-data-sync` — **2 раза в сутки**, 03:00 и 15:00 (`crontab(hour=3/15, minute=0)`). Это полный синк, который пишет в `product_daily_stats`. **Запрашивает 30 дней назад**.

### D. Известные проблемы и долги
- **WB Statistics API за 1-5 мая 2026**: эндпоинт `/sales-funnel/products/history` либо не отдаёт данные за майские праздники (нормальная задержка 1-2 дня), либо возвращает 429 Too Many Requests при многократных запросах. В `product_daily_stats` максимальная дата = 2026-04-30. Ожидается автозаполнение в 03:00 6.05.2026.
- WB также возвращает `400 invalid start day: excess limit on days` для запросов глубже ~7 дней назад на этом эндпоинте — функция `daily_data_sync` запрашивает 30 дней и падает на старых окнах. **TODO**: ограничить `_daily_sync` синхронизацией последних 7 дней.
- В `stats_collector.py` отсутствует метод `get_normquery_stats` у `WBClient` (`AttributeError`) — рекламная статистика по нормозапросам не собирается. **TODO**: реализовать или временно закомментировать вызов.
- В `sync_products_and_dimensions` не определён `wh_coefs` (`NameError`). **TODO**: проверить импорт/инициализацию.
- Бандл фронта 1.55 MB (gzip 472 KB). Нужно code-splitting (Vite warning).
- Доустановлен пакет `pytz` — был `ModuleNotFoundError` в `app/services/scheduler.py`.

### E. Файлы изменены / созданы
- backend: `app/models/monthly_plan.py` (новый), `app/models/__init__.py`, `app/services/plan_fact.py` (новый), `app/api/plan_fact.py` (новый), `app/main.py`, `alembic/versions/437bceeccdd8_add_monthly_plans.py` (новый).
- frontend: `src/pages/PlanFact.tsx` (новый), `src/pages/Margin.tsx`, `src/api/client.ts`, `src/App.tsx`.
- БД: миграция применена (`alembic current` → `437bceeccdd8`).

### F. Следующая итерация
1. Дождаться автоматического синка 6.05 в 03:00 — убедиться что 1-5 мая попали в `product_daily_stats`.
2. Починить `daily_data_sync`: уменьшить окно с 30 до 7 дней.
3. На странице «План/Факт» добавить накопительный график (Recharts) с переключателем «Выручка / Маржа / Заказы»: линия плана, кривая факта, пунктир прогноза.
4. Добавить страницу «План по SKU» — таблица 192 артикулов с полями плана на месяц (структура из Google-таблицы пользователя).

---

## Сессия 2026-06-08 — модуль Locator

Спроектирован модуль контроля локализации и остатков для бренда BALGINI.
Полная архитектура: см. LOCATOR.md

### Что сделано
- Диагностика сервера, очистка диска (86% -> 76%)
- Изучен WB API: warehouse_remains + sales-funnel (localizationPercent)
- Собраны бизнес-требования: 19 баркодов, константы, таблица КТР/КРП
- Спроектирована архитектура: 6 сервисов, 12 эндпоинтов, 7 моделей БД

### Следующие шаги
1. Получить WB API токен и вставить в .env
2. Создать Alembic-миграцию для таблиц Locator
3. Реализовать backend-сервисы
4. Реализовать frontend-дашборд
