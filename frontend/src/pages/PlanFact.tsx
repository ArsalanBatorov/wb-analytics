/**
 * Страница «План/Факт» — редизайн в стиле B2B-дашборда (плотность, цифры, аналитика).
 *
 * Блоки:
 *  1. Шапка: заголовок, подзаголовок, период, кнопка перезагрузки
 *  2. KPI-cards: 6 верхних карточек по метрикам из summary.metrics
 *  3. Селектор периода + ввод плана на месяц
 *  4. Кумулятивный график Recharts (план / факт / прогноз)
 *  5. Матрица показателей — компактная таблица с tabular-nums и conditional formatting
 *  6. Таблица SKU — фото WB, поиск, итоговая строка, раскраска DRR/маржи
 */
import { useEffect, useMemo, useState, useCallback } from "react";
import {
  ConfigProvider, Layout, Typography, Card, Row, Col, Radio,
  DatePicker, Spin, Table, Tag, InputNumber, Button, Space,
  Divider, message, Input,
} from "antd";
import {
  ReloadOutlined, SearchOutlined, RiseOutlined, FallOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import dayjs, { Dayjs } from "dayjs";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Area,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import {
  fetchPlanFactSummary, fetchPlanFactProducts,
  fetchMonthlyPlan, updateMonthlyPlan,
  type PlanFactSummary, type PlanFactProduct, type MonthlyPlan,
} from "../api/client";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

/* ---------- formatters ---------- */
const fmt = (v: number | null | undefined, suffix = "") => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(v) + suffix;
};
const fmt2 = (v: number | null | undefined, suffix = "") => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(v) + suffix;
};

const pctTag = (pct: number | null) => {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return <Text type="secondary">—</Text>;
  let color = "default";
  if (pct >= 95) color = "green";
  else if (pct >= 80) color = "gold";
  else if (pct > 0) color = "red";
  return <Tag color={color} style={{ fontVariantNumeric: "tabular-nums" }}>{fmt2(pct, "%")}</Tag>;
};

const pctBadge = (pct: number | null) => {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return <span style={{ color: "#8c8c8c", fontSize: 12 }}>—</span>;
  const isPos = pct >= 80;
  return (
    <span style={{ color: isPos ? "#389e0d" : "#cf1322", fontSize: 12, fontWeight: 500, display: "inline-flex", alignItems: "center", gap: 2 }}>
      {isPos ? <RiseOutlined /> : <FallOutlined />}
      {fmt2(pct, "%")}
    </span>
  );
};

/* ---------- theme tokens (compact B2B) ---------- */
const compactTheme = {
  token: {
    borderRadius: 4,
    colorBgContainer: "#ffffff",
    colorText: "#1f1f1f",
    colorTextSecondary: "#595959",
    fontSize: 13,
  },
  components: {
    Card: {
      headerHeight: 40,
      paddingLG: 12,
    } as any,
    Table: {
      padding: 8,
      paddingSM: 6,
      paddingXS: 4,
      fontSize: 12,
    } as any,
    Input: {
      paddingInline: 8,
    } as any,
    InputNumber: {
      paddingInline: 8,
    } as any,
  },
};

/* ---------- helpers ---------- */
const wbImageUrl = (nmId: number) => {
  const basket = Math.floor(nmId / 10000) * 10000;
  return `https://images.wbstatic.net/c246x328/new/${basket}/${nmId}-1.jpg`;
};

const kpiIcon = (key: string) => {
  if (key === "drr") return <ExclamationCircleOutlined style={{ color: "#fa8c16" }} />;
  if (key.includes("margin")) return <RiseOutlined style={{ color: "#1890ff" }} />;
  return <RiseOutlined style={{ color: "#52c41a" }} />;
};

/* ---------- cumulative chart data builder ---------- */
interface CumulativePoint {
  day: number;
  label: string;
  plan: number;
  fact: number;
  forecast: number;
}

function buildCumulative(summary: PlanFactSummary | null): CumulativePoint[] {
  if (!summary) return [];
  const m = summary.metrics.find((x) => x.key === "orders_revenue") || summary.metrics[0];
  if (!m) return [];
  const daysInMonth = summary.days_in_month || 30;
  const factDays = summary.fact_days || 1;
  const planTotal = m.plan_total ?? 0;
  const factTotal = m.fact_total ?? 0;
  const forecastTotal = m.forecast ?? 0;
  const planDaily = planTotal / daysInMonth;
  const factDaily = factTotal / factDays;
  const forecastRemain = Math.max(0, forecastTotal - factTotal);
  const remainDays = Math.max(1, daysInMonth - factDays);
  const forecastDaily = forecastRemain / remainDays;

  const out: CumulativePoint[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const planVal = planDaily * d;
    const factVal = d <= factDays ? factDaily * d : factTotal;
    const forecastVal = d <= factDays ? factDaily * d : factTotal + forecastDaily * (d - factDays);
    out.push({
      day: d,
      label: `${d}`,
      plan: Math.round(planVal),
      fact: Math.round(factVal),
      forecast: Math.round(forecastVal),
    });
  }
  return out;
}

const ChartTooltip = ({ active, payload, label }: TooltipProps<ValueType, NameType>) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#fff", border: "1px solid #f0f0f0", padding: "8px 12px", borderRadius: 4, fontSize: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>День {label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color as string }} />
          <span style={{ color: "#595959" }}>{p.name}:</span>
          <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>{fmt(Number(p.value), " ₽")}</span>
        </div>
      ))}
    </div>
  );
};

/* ==================== COMPONENT ==================== */
export default function PlanFact() {
  /* ---- period ---- */
  const [preset, setPreset] = useState<number | "custom" | "month">("month");
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);

  const [dateFrom, dateTo] = useMemo(() => {
    if (preset === "custom" && range) {
      return [range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD")];
    }
    if (preset === "month") {
      return [dayjs().startOf("month").format("YYYY-MM-DD"), dayjs().format("YYYY-MM-DD")];
    }
    if (preset === 1) {
      const y = dayjs().subtract(1, "day").format("YYYY-MM-DD");
      return [y, y];
    }
    const days = preset as number;
    return [
      dayjs().subtract(days - 1, "day").format("YYYY-MM-DD"),
      dayjs().format("YYYY-MM-DD"),
    ];
  }, [preset, range]);

  /* ---- plan month ---- */
  const [planMonth, setPlanMonth] = useState<string>(dayjs().startOf("month").format("YYYY-MM-DD"));

  /* ---- data ---- */
  const [summary, setSummary] = useState<PlanFactSummary | null>(null);
  const [products, setProducts] = useState<PlanFactProduct[]>([]);
  const [plan, setPlan] = useState<MonthlyPlan | null>(null);
  const [loading, setLoading] = useState(false);

  /* ---- plan form ---- */
  const [planForm, setPlanForm] = useState({
    plan_orders_qty: 0,
    plan_orders_revenue: 0,
    plan_buyouts_qty: 0,
    plan_buyouts_revenue: 0,
    plan_margin: 0,
  });
  const [savingPlan, setSavingPlan] = useState(false);

  /* ---- SKU search ---- */
  const [search, setSearch] = useState("");

  /* ---- load ---- */
  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetchPlanFactSummary({ date_from: dateFrom, date_to: dateTo }, planMonth),
      fetchPlanFactProducts({ date_from: dateFrom, date_to: dateTo }),
      fetchMonthlyPlan(planMonth),
    ])
      .then(([s, p, pl]) => {
        setSummary(s);
        setProducts(p);
        setPlan(pl);
        setPlanForm({
          plan_orders_qty: pl.plan_orders_qty,
          plan_orders_revenue: pl.plan_orders_revenue,
          plan_buyouts_qty: pl.plan_buyouts_qty,
          plan_buyouts_revenue: pl.plan_buyouts_revenue,
          plan_margin: pl.plan_margin,
        });
      })
      .catch((e) => {
        console.error(e);
        message.error("Ошибка загрузки данных");
      })
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo, planMonth]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /* ---- save plan ---- */
  const savePlan = async () => {
    setSavingPlan(true);
    try {
      const updated = await updateMonthlyPlan({ month: planMonth, ...planForm });
      setPlan(updated);
      message.success("План сохранён");
      const s = await fetchPlanFactSummary({ date_from: dateFrom, date_to: dateTo }, planMonth);
      setSummary(s);
    } catch (e) {
      console.error(e);
      message.error("Ошибка сохранения плана");
    } finally {
      setSavingPlan(false);
    }
  };

  /* ---- filtered products ---- */
  const filteredProducts = useMemo(() => {
    if (!search.trim()) return products;
    const s = search.toLowerCase();
    return products.filter(
      (p) =>
        p.vendor_code?.toLowerCase().includes(s) ||
        p.title?.toLowerCase().includes(s) ||
        String(p.nm_id).includes(s)
    );
  }, [products, search]);

  /* ---- chart data ---- */
  const chartData = useMemo(() => buildCumulative(summary), [summary]);

  /* ---- KPI cards data ---- */
  const kpiMetrics = useMemo(() => summary?.metrics ?? [], [summary]);

  /* ---- matrix columns (compact, right-aligned, tabular-nums) ---- */
  const matrixColumns = useMemo(
    () => [
      {
        title: "Метрика",
        dataIndex: "title",
        key: "title",
        width: 180,
        fixed: "left" as const,
        render: (v: string) => <b style={{ fontSize: 13 }}>{v}</b>,
      },
      {
        title: "План ср/день",
        dataIndex: "plan_per_day",
        key: "plan_per_day",
        width: 130,
        align: "right" as const,
        render: (v: number | null, row: any) =>
          row.key === "drr"
            ? "—"
            : (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                  {row.key.includes("qty") ? fmt2(v) : fmt(v, " ₽")}
                </span>
              ),
      },
      {
        title: "Факт ср/день",
        dataIndex: "fact_per_day",
        key: "fact_per_day",
        width: 130,
        align: "right" as const,
        render: (v: number | null, row: any) =>
          row.key === "drr"
            ? (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13, color: v && v > 15 ? "#cf1322" : "inherit" }}>
                  {fmt2(v, "%")}
                </span>
              )
            : (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                  {row.key.includes("qty") ? fmt2(v) : fmt(v, " ₽")}
                </span>
              ),
      },
      {
        title: "Прогноз на мес",
        dataIndex: "forecast",
        key: "forecast",
        width: 140,
        align: "right" as const,
        render: (v: number | null, row: any) =>
          row.key === "drr"
            ? (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13, color: v && v > 15 ? "#cf1322" : "inherit" }}>
                  {fmt2(v, "%")}
                </span>
              )
            : (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                  {row.key.includes("qty") ? fmt(v) : fmt(v, " ₽")}
                </span>
              ),
      },
      {
        title: "План общий",
        dataIndex: "plan_total",
        key: "plan_total",
        width: 130,
        align: "right" as const,
        render: (v: number | null, row: any) =>
          row.key === "drr"
            ? "—"
            : (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                  {row.key.includes("qty") ? fmt(v) : fmt(v, " ₽")}
                </span>
              ),
      },
      {
        title: "Факт общий",
        dataIndex: "fact_total",
        key: "fact_total",
        width: 130,
        align: "right" as const,
        render: (v: number | null, row: any) =>
          row.key === "drr"
            ? (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13, color: v && v > 15 ? "#cf1322" : "inherit" }}>
                  {fmt2(v, "%")}
                </span>
              )
            : (
                <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
                  {row.key.includes("qty") ? fmt(v) : fmt(v, " ₽")}
                </span>
              ),
      },
      {
        title: "% выполн",
        dataIndex: "pct",
        key: "pct",
        width: 110,
        align: "center" as const,
        render: (v: number | null) => pctTag(v),
      },
    ],
    []
  );

  /* ---- SKU columns ---- */
  const skuColumns = useMemo(
    () => [
      {
        title: "Фото",
        key: "photo",
        width: 60,
        fixed: "left" as const,
        render: (_: any, row: PlanFactProduct) => (
          <img
            src={wbImageUrl(row.nm_id)}
            alt={row.vendor_code || String(row.nm_id)}
            style={{ width: 40, height: 40, borderRadius: 4, objectFit: "cover", display: "block" }}
            loading="lazy"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        ),
      },
      {
        title: "Артикул",
        dataIndex: "vendor_code",
        key: "vendor_code",
        width: 120,
        fixed: "left" as const,
        render: (v: string) => <b style={{ fontSize: 12 }}>{v || "—"}</b>,
      },
      {
        title: "nm_id",
        dataIndex: "nm_id",
        key: "nm_id",
        width: 110,
        render: (v: number) => (
          <a href={`https://www.wildberries.ru/catalog/${v}/detail.aspx`} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
            {v}
          </a>
        ),
      },
      {
        title: "Название",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        width: 260,
        render: (v: string) => <span style={{ fontSize: 12 }}>{v}</span>,
      },
      {
        title: "Заказы, шт",
        dataIndex: "orders_qty",
        key: "orders_qty",
        width: 110,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.orders_qty - b.orders_qty,
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(v)}</span>,
      },
      {
        title: "Заказы, ₽",
        dataIndex: "orders_revenue",
        key: "orders_revenue",
        width: 120,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.orders_revenue - b.orders_revenue,
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(v, " ₽")}</span>,
      },
      {
        title: "Выкупы, шт",
        dataIndex: "buyouts_qty",
        key: "buyouts_qty",
        width: 110,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.buyouts_qty - b.buyouts_qty,
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(v)}</span>,
      },
      {
        title: "Выкупы, ₽",
        dataIndex: "buyouts_revenue",
        key: "buyouts_revenue",
        width: 120,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.buyouts_revenue - b.buyouts_revenue,
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(v, " ₽")}</span>,
      },
      {
        title: "Маржа",
        dataIndex: "margin",
        key: "margin",
        width: 120,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.margin - b.margin,
        defaultSortOrder: "descend" as const,
        render: (v: number) => (
          <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12, color: v < 0 ? "#cf1322" : "#389e0d", fontWeight: 500 }}>
            {fmt(v, " ₽")}
          </span>
        ),
      },
      {
        title: "Реклама",
        dataIndex: "ad_spend",
        key: "ad_spend",
        width: 110,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.ad_spend - b.ad_spend,
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(v, " ₽")}</span>,
      },
      {
        title: "ДРР %",
        dataIndex: "drr",
        key: "drr",
        width: 90,
        align: "right" as const,
        sorter: (a: PlanFactProduct, b: PlanFactProduct) => a.drr - b.drr,
        render: (v: number) => (
          <span
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: 12,
              fontWeight: 500,
              color: v > 15 ? "#cf1322" : v > 8 ? "#fa8c16" : "#389e0d",
            }}
          >
            {fmt2(v, "%")}
          </span>
        ),
      },
    ],
    []
  );

  /* ---- SKU summary row ---- */
  const skuSummary = useMemo(() => {
    return filteredProducts.reduce(
      (acc, p) => ({
        orders_qty: acc.orders_qty + p.orders_qty,
        orders_revenue: acc.orders_revenue + p.orders_revenue,
        buyouts_qty: acc.buyouts_qty + p.buyouts_qty,
        buyouts_revenue: acc.buyouts_revenue + p.buyouts_revenue,
        margin: acc.margin + p.margin,
        ad_spend: acc.ad_spend + p.ad_spend,
      }),
      { orders_qty: 0, orders_revenue: 0, buyouts_qty: 0, buyouts_revenue: 0, margin: 0, ad_spend: 0 }
    );
  }, [filteredProducts]);

  const avgDrr = useMemo(() => {
    if (!filteredProducts.length) return 0;
    return filteredProducts.reduce((s, p) => s + p.drr, 0) / filteredProducts.length;
  }, [filteredProducts]);

  return (
    <ConfigProvider theme={compactTheme}>
      <Layout.Content style={{ padding: 16, background: "#F5F6F8" }}>
        <Spin spinning={loading}>
          {/* ===== HEADER ===== */}
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
            <div>
              <Title level={3} style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>План/Факт</Title>
              <Text type="secondary" style={{ fontSize: 12 }}>План/факт аналитика · {dateFrom} — {dateTo}</Text>
            </div>
            <Space>
              <Tag style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                {summary?.fact_days ?? "—"} / {summary?.days_in_month ?? "—"} дн
              </Tag>
              <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} size="small">
                Обновить
              </Button>
            </Space>
          </div>

          {/* ===== KPI CARDS ===== */}
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {kpiMetrics.map((m) => (
              <Col xs={12} sm={12} md={8} lg={4} key={m.key}>
                <Card
                  size="small"
                  styles={{ body: { padding: "12px 16px" } }}
                  style={{ borderRadius: 8 }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    {kpiIcon(m.key)}
                    <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.3 }}>
                      {m.title}
                    </Text>
                  </div>
                  <div
                    style={{
                      fontSize: 22,
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                      lineHeight: 1.2,
                      marginBottom: 6,
                    }}
                  >
                    {m.key === "drr"
                      ? fmt2(m.fact_total, "%")
                      : m.key.includes("qty")
                        ? fmt(m.fact_total)
                        : fmt(m.fact_total, " ₽")}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Text type="secondary" style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
                      План:{" "}
                      {m.plan_total !== null && m.plan_total !== undefined
                        ? m.key.includes("qty")
                          ? fmt(m.plan_total)
                          : fmt(m.plan_total, " ₽")
                        : "—"}
                    </Text>
                    {pctBadge(m.pct)}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          {/* ===== PERIOD + PLAN INPUT ===== */}
          <Card size="small" style={{ marginBottom: 16, borderRadius: 8 }}>
            <Space wrap size="middle" align="center">
              <Radio.Group
                value={preset}
                onChange={(e) => setPreset(e.target.value)}
                size="small"
              >
                <Radio.Button value={1}>Вчера</Radio.Button>
                <Radio.Button value={7}>7 дней</Radio.Button>
                <Radio.Button value={14}>14 дней</Radio.Button>
                <Radio.Button value={30}>30 дней</Radio.Button>
                <Radio.Button value="month">Тек. месяц</Radio.Button>
                <Radio.Button value="custom">Свой</Radio.Button>
              </Radio.Group>
              {preset === "custom" && (
                <RangePicker
                  value={range as any}
                  onChange={(r) => setRange(r as any)}
                  format="YYYY-MM-DD"
                  size="small"
                />
              )}
              <Divider type="vertical" style={{ margin: "0 4px" }} />
              <Text style={{ fontSize: 12 }}>Месяц плана:</Text>
              <DatePicker
                picker="month"
                value={dayjs(planMonth)}
                onChange={(d) => d && setPlanMonth(d.startOf("month").format("YYYY-MM-DD"))}
                format="MMMM YYYY"
                size="small"
              />
            </Space>

            <Divider style={{ margin: "12px 0" }} />

            <Row gutter={[12, 12]} align="bottom">
              <Col xs={12} sm={8} md={4}>
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 2 }}>
                  Заказы, ₽
                </Text>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={10000}
                  size="small"
                  value={planForm.plan_orders_revenue}
                  onChange={(v) => setPlanForm({ ...planForm, plan_orders_revenue: v ?? 0 })}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, " ")}
                  parser={(v) => Number((v ?? "").toString().replace(/[\s\u00a0]/g, "").replace(",", "."))}
                  decimalSeparator=","
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 2 }}>
                  Выкупы, ₽
                </Text>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={10000}
                  size="small"
                  value={planForm.plan_buyouts_revenue}
                  onChange={(v) => setPlanForm({ ...planForm, plan_buyouts_revenue: v ?? 0 })}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, " ")}
                  parser={(v) => Number((v ?? "").toString().replace(/[\s\u00a0]/g, "").replace(",", "."))}
                  decimalSeparator=","
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 2 }}>
                  Заказы, шт
                </Text>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={10}
                  size="small"
                  value={planForm.plan_orders_qty}
                  onChange={(v) => setPlanForm({ ...planForm, plan_orders_qty: v ?? 0 })}
                  parser={(v) => Number((v ?? "").toString().replace(/[\s\u00a0]/g, "").replace(",", "."))}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 2 }}>
                  Выкупы, шт
                </Text>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={1}
                  size="small"
                  value={planForm.plan_buyouts_qty}
                  onChange={(v) => setPlanForm({ ...planForm, plan_buyouts_qty: v ?? 0 })}
                  parser={(v) => Number((v ?? "").toString().replace(/[\s\u00a0]/g, "").replace(",", "."))}
                />
              </Col>
              <Col xs={12} sm={8} md={4}>
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 2 }}>
                  Валовая прибыль, ₽
                </Text>
                <InputNumber
                  style={{ width: "100%" }}
                  min={-9999999}
                  step={10000}
                  size="small"
                  value={planForm.plan_margin}
                  onChange={(v) => setPlanForm({ ...planForm, plan_margin: v ?? 0 })}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, " ")}
                  parser={(v) => Number((v ?? "").toString().replace(/[\s\u00a0]/g, "").replace(",", "."))}
                  decimalSeparator=","
                />
              </Col>
              <Col xs={24} sm={24} md={4}>
                <Button type="primary" loading={savingPlan} onClick={savePlan} block size="small">
                  {plan?.exists ? "Обновить план" : "Сохранить план"}
                </Button>
              </Col>
            </Row>
          </Card>

          {/* ===== CHART ===== */}
          {chartData.length > 0 && (
            <Card
              size="small"
              title="Кумулятивная динамика (выручка заказов)"
              style={{ marginBottom: 16, borderRadius: 8 }}
            >
              <div style={{ width: "100%", height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="#bfbfbf" />
                    <YAxis
                      tick={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}
                      stroke="#bfbfbf"
                      tickFormatter={(v: number) => fmt(v, " ₽")}
                      width={90}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Area
                      type="monotone"
                      dataKey="plan"
                      stroke="#1890ff"
                      fill="#1890ff"
                      fillOpacity={0.06}
                      strokeWidth={2}
                      dot={false}
                      name="План"
                    />
                    <Line
                      type="monotone"
                      dataKey="fact"
                      stroke="#52c41a"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                      name="Факт"
                    />
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      stroke="#fa8c16"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={false}
                      name="Прогноз"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* ===== MATRIX ===== */}
          <Card
            size="small"
            title="Матрица показателей"
            style={{ marginBottom: 16, borderRadius: 8 }}
          >
            <Table
              size="small"
              rowKey="key"
              columns={matrixColumns}
              dataSource={summary?.metrics ?? []}
              pagination={false}
              scroll={{ x: 1000 }}
              bordered
            />
          </Card>

          {/* ===== SKU TABLE ===== */}
          <Card
            size="small"
            title={
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span>SKU ({filteredProducts.length} / {products.length})</span>
                <Input
                  size="small"
                  placeholder="Поиск по артикулу, названию, nm_id"
                  prefix={<SearchOutlined />}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ width: 280 }}
                  allowClear
                />
              </div>
            }
            style={{ borderRadius: 8 }}
          >
            <Table
              size="small"
              rowKey="nm_id"
              columns={skuColumns}
              dataSource={filteredProducts}
              pagination={{ defaultPageSize: 25, showSizeChanger: true, pageSizeOptions: ["25", "50", "100", "200"] }}
              scroll={{ x: 1600 }}
              bordered
              summary={() => (
                <Table.Summary fixed="bottom">
                  <Table.Summary.Row style={{ background: "#fafafa", fontWeight: 600 }}>
                    <Table.Summary.Cell index={0} colSpan={3}>
                      <span style={{ fontSize: 12 }}>Итого ({filteredProducts.length})</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={3} align="right">
                      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(skuSummary.orders_qty)}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={4} align="right">
                      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(skuSummary.orders_revenue, " ₽")}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={5} align="right">
                      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(skuSummary.buyouts_qty)}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={6} align="right">
                      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(skuSummary.buyouts_revenue, " ₽")}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={7} align="right">
                      <span
                        style={{
                          fontVariantNumeric: "tabular-nums",
                          fontSize: 12,
                          color: skuSummary.margin < 0 ? "#cf1322" : "#389e0d",
                        }}
                      >
                        {fmt(skuSummary.margin, " ₽")}
                      </span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={8} align="right">
                      <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12 }}>{fmt(skuSummary.ad_spend, " ₽")}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={9} align="right">
                      <span
                        style={{
                          fontVariantNumeric: "tabular-nums",
                          fontSize: 12,
                          color: avgDrr > 15 ? "#cf1322" : avgDrr > 8 ? "#fa8c16" : "#389e0d",
                        }}
                      >
                        {fmt2(avgDrr, "%")}
                      </span>
                    </Table.Summary.Cell>
                  </Table.Summary.Row>
                </Table.Summary>
              )}
            />
          </Card>
        </Spin>
      </Layout.Content>
    </ConfigProvider>
  );
}
