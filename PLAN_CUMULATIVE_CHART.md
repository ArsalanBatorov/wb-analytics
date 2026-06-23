# План: Накопительный график на странице «План/Факт»

**Дата:** 2026-05-06  
**Объём:** ~80 строк backend + ~80 строк frontend  
**Затронутые файлы:** 4 файла, никаких миграций не нужно

---

## 1. Что нужно реализовать

На странице [`PlanFact.tsx`](frontend/src/pages/PlanFact.tsx) между матрицей и таблицей SKU добавить карточку с Recharts `ComposedChart`:

- **Переключатель**: Выручка (заказы ₽) / Маржа (валовая прибыль ₽) / Заказы (шт) — `Radio.Group`
- **Три кривых**:
  - **Линия плана** — прямая равномерная от 0 до `plan_total`, по всем дням выбранного месяца
  - **Кривая факта** — нарастающий итог фактических дней (накопительная сумма)
  - **Пунктир прогноза** — от последней точки факта до конца месяца (прямая: `cum_fact_last / days_elapsed * days_in_month`)

---

## 2. Backend

### Шаг 2.1 — Новая функция [`calc_plan_fact_daily`](backend/app/services/plan_fact.py)

Добавить в конец файла `backend/app/services/plan_fact.py`:

```python
async def calc_plan_fact_daily(
    db: AsyncSession, date_from: date, date_to: date, plan_month: date
) -> dict:
    """
    Возвращает ежедневные накопительные данные для графика.
    
    Выходной формат:
    {
      "plan_month_days": 31,
      "plan": {"orders_revenue": 10_000_000, "margin": 2_000_000, "orders_qty": 5000},
      "chart": [
        {
          "date": "2026-05-01",
          "day_of_month": 1,          # порядковый номер в месяце
          "fact_orders_revenue": 120000,
          "fact_margin": 25000,
          "fact_orders_qty": 65,
          "plan_orders_revenue": 322580,  # plan / days_in_month * day_of_month
          "plan_margin": 64516,
          "plan_orders_qty": 161,
          "forecast_orders_revenue": 3_200_000,  # только у последней точки, иначе null
          "forecast_margin": 650_000,
          "forecast_orders_qty": 1700,
        },
        ...
      ]
    }
    """
```

**Логика**:
1. `SELECT dt, SUM(order_sum), SUM(order_count), SUM(margin_profit) FROM product_daily_stats WHERE dt BETWEEN date_from AND date_to GROUP BY dt ORDER BY dt`
2. Накопительная сумма (cumsum) по каждой из 3 метрик
3. Для каждого `day_of_month` (1…days_in_month) добавить `plan_X = plan_total / days_in_month * day_of_month`
4. Прогноз рассчитывается только для точек **после** последней даты с факта: `forecast_X = cum_fact_last / days_elapsed * days_in_month`
5. Для дней с фактом `forecast_X = null`, для дней без факта `fact_X = null`

### Шаг 2.2 — Новый эндпоинт в [`plan_fact.py`](backend/app/api/plan_fact.py)

Добавить к `plan_fact_router`:

```python
@plan_fact_router.get("/daily")
async def plan_fact_daily(
    date_from: str = Query(...),
    date_to: str = Query(...),
    plan_month: str | None = Query(None),
):
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    pm = _parse_date(plan_month, "plan_month") if plan_month else _first_day_of_month(dt)
    async with async_session() as db:
        return await calc_plan_fact_daily(db, df, dt, pm)
```

---

## 3. Frontend

### Шаг 3.1 — Новая функция в [`client.ts`](frontend/src/api/client.ts)

```typescript
export interface ChartPoint {
  date: string;
  day_of_month: number;
  fact_orders_revenue: number | null;
  fact_margin: number | null;
  fact_orders_qty: number | null;
  plan_orders_revenue: number;
  plan_margin: number;
  plan_orders_qty: number;
  forecast_orders_revenue: number | null;
  forecast_margin: number | null;
  forecast_orders_qty: number | null;
}
export interface PlanFactDaily {
  plan_month_days: number;
  plan: { orders_revenue: number; margin: number; orders_qty: number };
  chart: ChartPoint[];
}

export async function fetchPlanFactDaily(
  params: { date_from: string; date_to: string },
  planMonth?: string
): Promise<PlanFactDaily> {
  const q = new URLSearchParams(params as any);
  if (planMonth) q.set("plan_month", planMonth);
  return apiFetch(`/plan-fact/daily?${q}`);
}
```

### Шаг 3.2 — Обновление [`PlanFact.tsx`](frontend/src/pages/PlanFact.tsx)

**Импорты** (добавить):
```typescript
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";
import { fetchPlanFactDaily, type PlanFactDaily } from "../api/client";
```

**State** (добавить):
```typescript
const [chartMetric, setChartMetric] = useState<"revenue" | "margin" | "orders">("revenue");
const [dailyData, setDailyData] = useState<PlanFactDaily | null>(null);
```

**useEffect** — добавить `fetchPlanFactDaily` в `Promise.all`:
```typescript
fetchPlanFactDaily({ date_from: dateFrom, date_to: dateTo }, planMonth)
  .then(setDailyData)
  .catch(console.error);
```

**Карточка графика** (вставить между матрицей и таблицей SKU):
```tsx
<Card size="small" title="Динамика месяца (нарастающий итог)" style={{ marginBottom: 16 }}
  extra={
    <Radio.Group value={chartMetric} size="small" onChange={e => setChartMetric(e.target.value)}>
      <Radio.Button value="revenue">Выручка</Radio.Button>
      <Radio.Button value="margin">Маржа</Radio.Button>
      <Radio.Button value="orders">Заказы</Radio.Button>
    </Radio.Group>
  }>
  <ResponsiveContainer width="100%" height={280}>
    <ComposedChart data={dailyData?.chart ?? []}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
      <YAxis tickFormatter={v => Intl.NumberFormat("ru-RU", { notation: "compact" }).format(v)} />
      <Tooltip formatter={(v: any) => Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(v)} />
      <Legend />
      {/* Линия плана — сплошная серая */}
      <Line type="linear" dataKey={`plan_${metricKey}`} name="План" stroke="#8c8c8c" dot={false} strokeWidth={2} />
      {/* Кривая факта — сплошная синяя */}
      <Line type="monotone" dataKey={`fact_${metricKey}`} name="Факт" stroke="#1890ff" dot={false} strokeWidth={2} connectNulls={false} />
      {/* Прогноз — пунктирная зелёная */}
      <Line type="linear" dataKey={`forecast_${metricKey}`} name="Прогноз" stroke="#52c41a" dot={false} strokeWidth={2} strokeDasharray="6 3" connectNulls={false} />
    </ComposedChart>
  </ResponsiveContainer>
</Card>
```

где `metricKey` = `chartMetric === "revenue" ? "orders_revenue" : chartMetric === "margin" ? "margin" : "orders_qty"`

---

## 4. Порядок реализации

| № | Файл | Действие |
|---|------|---------|
| 1 | `backend/app/services/plan_fact.py` | Добавить функцию `calc_plan_fact_daily` в конец файла |
| 2 | `backend/app/api/plan_fact.py` | Добавить эндпоинт `GET /plan-fact/daily` |
| 3 | `frontend/src/api/client.ts` | Добавить интерфейсы `ChartPoint`, `PlanFactDaily` и функцию `fetchPlanFactDaily` |
| 4 | `frontend/src/pages/PlanFact.tsx` | Добавить state, useEffect, карточку с графиком |
| 5 | Сервер | `systemctl restart wb-backend && cd /root/wb-analytics/frontend && npm run build && cp -r dist/* /var/www/wb-bidder/` |

---

## 5. Примечания

- График работает с **любым выбранным периодом** (`date_from..date_to`), не только с текущим месяцем.  
  Если период меньше месяца — линия плана отображается пропорционально.
- Если `product_daily_stats` пустой за выбранный период — карточка показывает пустой график, без ошибок.
- `connectNulls={false}` на Recharts нужен, чтобы не соединять факт с прогнозом через пустые дни.
- Backend не требует миграции — читает только существующие таблицы.
