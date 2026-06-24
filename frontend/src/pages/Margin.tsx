import { useEffect, useState, useMemo } from "react";
import {
  Card, Row, Col, DatePicker, Radio, Spin, Typography, Space, Tag, Alert,
} from "antd";
import {
  CaretUpOutlined, CaretDownOutlined, MinusOutlined, WarningOutlined,
} from "@ant-design/icons";
import dayjs, { Dayjs } from "dayjs";
import { fetchTruestatDashboard, TruestatDashboard } from "../api/client";

const { RangePicker } = DatePicker;
const { Title, Text } = Typography;

const fmt = (n: number) => (n ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
const fmtM = (n: number) => fmt(n) + " ₽";
const fmtP = (n: number) => (n ?? 0).toFixed(2) + "%";
const fmtP1 = (n: number) => (n ?? 0).toFixed(1) + "%";

interface MetricDef {
  key: string;
  title: string;
  subtitle?: string;
  format: "money" | "money_pct" | "pct" | "money_count" | "days" | "money_pct_revenue";
  good_when: "up" | "down";
}

const METRICS: MetricDef[] = [
  { key: "margin", title: "Прибыль", subtitle: "Чист. маржа", format: "money_pct", good_when: "up" },
  { key: "orders", title: "Заказы", format: "money_count", good_when: "up" },
  { key: "sales", title: "Продажи", format: "money_count", good_when: "up" },
  { key: "ad_spend", title: "Реклама / ДРР", format: "money_pct", good_when: "down" },
  { key: "logistics", title: "Логистика", format: "money_pct_revenue", good_when: "down" },
  { key: "buyout_rate", title: "Процент выкупа", format: "pct", good_when: "up" },
  { key: "storage", title: "Хранение", format: "money_pct_revenue", good_when: "down" },
  { key: "acceptance", title: "Плат. приёмка", format: "money_pct_revenue", good_when: "down" },
  { key: "penalty", title: "Штрафы", format: "money_pct_revenue", good_when: "down" },
  { key: "roi", title: "ROI", format: "pct", good_when: "up" },
  { key: "cogs", title: "Себестоимость продаж", format: "money_pct_revenue", good_when: "down" },
  { key: "taxes", title: "Налоги", format: "money_pct_revenue", good_when: "down" },
  { key: "commission", title: "Комиссия", format: "money_pct_revenue", good_when: "down" },
  { key: "avg_price_before_discount", title: "Сред. цена до скидок МП", format: "money", good_when: "up" },
  { key: "capitalization_cogs", title: "Капитализация по себес.", format: "money", good_when: "up" },
  { key: "capitalization_retail", title: "Капитализация по розн.", format: "money", good_when: "up" },
  { key: "compensation", title: "Компенсации", format: "money_pct_revenue", good_when: "up" },
  { key: "avg_sale_price", title: "Сред. цена продажи", format: "money", good_when: "up" },
  { key: "drr_orders", title: "Реклама/ДРРз", format: "money_pct", good_when: "down" },
  { key: "avg_logistics_per_item", title: "Ср. стоимость логистики на 1 шт", format: "money", good_when: "down" },
  { key: "turnover_days_sales", title: "Оборачиваемость по прод.", format: "days", good_when: "down" },
  { key: "turnover_days_orders", title: "Оборачиваемость по зак.", format: "days", good_when: "down" },
];

function MetricValue({ m, v }: { m: MetricDef; v: any }) {
  switch (m.format) {
    case "money_pct":
      return (
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtM(v?.value ?? 0)}</div>
          <Text type="secondary" style={{ fontSize: 13 }}>/ {fmtP(v?.value_pct ?? 0)}</Text>
        </div>
      );
    case "money_pct_revenue":
      return (
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtM(v?.value ?? 0)}</div>
          <Text type="secondary" style={{ fontSize: 13 }}>/ {fmtP(v?.value_pct ?? 0)}</Text>
        </div>
      );
    case "money_count":
      return (
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtM(v?.value ?? 0)}</div>
          <Text type="secondary" style={{ fontSize: 13 }}>/ {fmt(v?.value_count ?? 0)} шт</Text>
        </div>
      );
    case "money":
      return <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtM(v?.value ?? 0)}</div>;
    case "pct":
      return <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtP1(v?.value_pct ?? 0)}</div>;
    case "days":
      return <div style={{ fontSize: 20, fontWeight: 600 }}>{fmt(v?.value ?? 0)} дн</div>;
    default:
      return <div style={{ fontSize: 20, fontWeight: 600 }}>{v?.value ?? 0}</div>;
  }
}

function DeltaDisplay({ deltaAbs, deltaPct, goodWhen }: { deltaAbs: number; deltaPct: number; goodWhen: "up" | "down" }) {
  if (Math.abs(deltaAbs) < 0.01) {
    return <MinusOutlined style={{ color: "#999", fontSize: 12 }} />;
  }
  const isUp = deltaAbs > 0;
  const isGood = (isUp && goodWhen === "up") || (!isUp && goodWhen === "down");
  const color = isGood ? "#52c41a" : "#ff4d4f";
  return (
    <span style={{ color, fontSize: 13, whiteSpace: "nowrap" }}>
      {isUp ? <CaretUpOutlined /> : <CaretDownOutlined />}
      {" "}{fmt(Math.abs(deltaAbs))} ({deltaPct >= 0 ? "+" : ""}{fmtP1(deltaPct)})
    </span>
  );
}

const STORAGE_PRESET = "margin_period_preset";
const STORAGE_RANGE = "margin_custom_range";

function restoreRange(): [Dayjs, Dayjs] {
  try {
    const saved = sessionStorage.getItem(STORAGE_RANGE);
    if (saved) {
      const [a, b] = JSON.parse(saved);
      return [dayjs(a), dayjs(b)];
    }
  } catch { /* ignore */ }
  return [dayjs().subtract(6, "day"), dayjs()];
}

export default function Margin() {
  const [preset, setPreset] = useState<number | "month" | "custom">(() => {
    const saved = sessionStorage.getItem(STORAGE_PRESET);
    if (saved === "month" || saved === "custom") return saved;
    const n = Number(saved);
    return n > 0 ? n : 7;
  });
  const [range, setRange] = useState<[Dayjs, Dayjs]>(restoreRange);
  const [data, setData] = useState<TruestatDashboard | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_PRESET, String(preset));
  }, [preset]);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_RANGE, JSON.stringify(range.map(d => d.format("YYYY-MM-DD"))));
  }, [range]);

  const [dateFrom, dateTo] = useMemo(() => {
    if (preset === "custom") return [range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD")];
    if (preset === "month") return [dayjs().startOf("month").format("YYYY-MM-DD"), dayjs().format("YYYY-MM-DD")];
    if (preset === 1) {
      const y = dayjs().subtract(1, "day").format("YYYY-MM-DD");
      return [y, y];
    }
    return [dayjs().subtract((preset as number) - 1, "day").format("YYYY-MM-DD"),
            dayjs().format("YYYY-MM-DD")];
  }, [preset, range]);

  useEffect(() => {
    setLoading(true);
    fetchTruestatDashboard({ date_from: dateFrom, date_to: dateTo })
      .then(setData)
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo, preset]);

  const m = data?.metrics;
  const deltaAbs = m?._delta_abs ?? {};
  const deltaPct = m?._delta_pct ?? {};
  const prev = m?._prev ?? {};

  const rows = useMemo(() => {
    const r: MetricDef[][] = [];
    for (let i = 0; i < METRICS.length; i += 5) {
      r.push(METRICS.slice(i, i + 5));
    }
    return r;
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <Title level={3} style={{ marginTop: 0 }}>Фин. отчёт</Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Radio.Group value={preset} onChange={e => setPreset(e.target.value)}>
            <Radio.Button value={1}>Вчера</Radio.Button>
            <Radio.Button value={7}>7 дней</Radio.Button>
            <Radio.Button value={14}>14 дней</Radio.Button>
            <Radio.Button value={30}>30 дней</Radio.Button>
            <Radio.Button value="month">Тек. месяц</Radio.Button>
            <Radio.Button value="custom">Свой</Radio.Button>
          </Radio.Group>
          {preset === "custom" && (
            <RangePicker value={range} onChange={(v) => v && setRange(v as [Dayjs, Dayjs])} />
          )}
          <span style={{ color: "#888" }}>{dateFrom} — {dateTo}</span>
          {data && (
            <Tag>{data.prev_period.date_from} — {data.prev_period.date_to}</Tag>
          )}
        </Space>
      </Card>

      {data?.data_warnings?.orders_unavailable && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message="Данные по заказам и рекламе за этот период ещё загружаются (задержка WB API 1-3 дня). Показатели (Заказы, Реклама, ROI) временно = 0."
          style={{ marginBottom: 12, fontSize: 13 }}
        />
      )}
      {data?.data_warnings?.avg_price_discount_fallback && (
        <Alert
          type="info"
          showIcon
          message="Средняя цена до скидок МП — оценка из карточки товара"
          style={{ marginBottom: 12, fontSize: 13 }}
        />
      )}

      <Spin spinning={loading}>
        {rows.map((row, ri) => (
          <Row gutter={[8, 8]} key={ri} style={{ marginBottom: 8 }}>
            {row.map((metric) => {
              const cv = m?.[metric.key];
              const da = deltaAbs[metric.key];
              const dp = deltaPct[metric.key];
              const isGood = da !== undefined && (
                (da > 0 && metric.good_when === "up") ||
                (da < 0 && metric.good_when === "down") ||
                Math.abs(da) < 0.01
              );
              const bgColor = da === undefined ? "#fff"
                : Math.abs(da) < 0.01 ? "#fafafa"
                : isGood ? "#f6ffed" : "#fff2f0";
              const borderColor = da === undefined ? "#f0f0f0"
                : Math.abs(da) < 0.01 ? "#f0f0f0"
                : isGood ? "#b7eb8f" : "#ffccc7";

              return (
                <Col xs={24} sm={12} md={8} lg={4} key={metric.key}>
                  <Card
                    size="small"
                    style={{
                      background: bgColor,
                      borderLeft: `3px solid ${borderColor}`,
                      height: "100%",
                    }}
                    styles={{ body: { padding: "8px 12px" } }}
                  >
                    <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                      {metric.title}
                      {metric.subtitle && (
                        <Text type="secondary" style={{ fontSize: 11, display: "block" }}>
                          {metric.subtitle}
                        </Text>
                      )}
                    </div>
                    <MetricValue m={metric} v={cv} />
                    {da !== undefined && (
                      <div style={{ marginTop: 4 }}>
                        <DeltaDisplay deltaAbs={da} deltaPct={dp} goodWhen={metric.good_when} />
                      </div>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        ))}
      </Spin>
    </div>
  );
}
