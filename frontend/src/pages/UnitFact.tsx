import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Table, Card, Tag, Space, Typography, Radio, DatePicker,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface UnitFactRow {
  vendor_code: string;
  sales_count: number;
  returns_count: number;
  returns_pct: number;
  net_sales: number;
  revenue: number;
  revenue_per_unit: number;
  cost_price_total: number;
  cost_price_per_unit: number;
  cost_price_pct: number;
  commission: number;
  commission_pct: number;
  logistics_total: number;
  logistics_per_unit: number;
  logistics_pct: number;
  logistics_direct: number;
  logistics_direct_pct: number;
  logistics_return: number;
  logistics_return_pct: number;
  acquiring_penalty: number;
  ad_spend: number;
  ad_spend_per_unit: number;
  margin_per_unit: number;
  margin_pct: number;
  roi: number;
  stock_wb: number;
  stock_in_transit: number;
  stock_days: number;
  avg_sales_per_week: number;
  turnover_days: number;
}

const fmt = (v: number | null | undefined, digits = 2): string => {
  if (v == null) return "-";
  return v.toLocaleString("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const fmtPct = (v: number | null | undefined): string => {
  if (v == null) return "-";
  return (v * 100).toFixed(1) + "%";
};

const fmtMoney = (v: number | null | undefined): string => {
  if (v == null || v === 0) return "-";
  return fmt(v) + " \u20BD";
};

const columns: ColumnsType<UnitFactRow> = [
  { title: "Артикул", dataIndex: "vendor_code", key: "vendor_code", width: 140, fixed: "left" },
  { title: "Продажи", dataIndex: "sales_count", key: "sales_count", width: 70, sorter: (a, b) => a.sales_count - b.sales_count, render: (v: number) => v > 0 ? v : "-" },
  { title: "Возвраты", dataIndex: "returns_count", key: "returns_count", width: 70, render: (v: number) => v > 0 ? v : "-" },
  { title: "% возвр", dataIndex: "returns_pct", key: "returns_pct", width: 70, render: fmtPct },
  { title: "Орг продажи", dataIndex: "net_sales", key: "net_sales", width: 70, sorter: (a, b) => a.net_sales - b.net_sales, render: (v: number) => v > 0 ? v : "-" },
  { title: "Выручка", dataIndex: "revenue", key: "revenue", width: 100, sorter: (a, b) => a.revenue - b.revenue, render: fmtMoney },
  { title: "Выручка на ед.", dataIndex: "revenue_per_unit", key: "revenue_per_unit", width: 100, render: fmtMoney },
  { title: "Себестоимость", dataIndex: "cost_price_total", key: "cost_price_total", width: 100, sorter: (a, b) => a.cost_price_total - b.cost_price_total, render: fmtMoney },
  { title: "Себ. на ед.", dataIndex: "cost_price_per_unit", key: "cost_price_per_unit", width: 90, render: fmtMoney },
  { title: "% себ.", dataIndex: "cost_price_pct", key: "cost_price_pct", width: 70, render: fmtPct },
  { title: "Комиссия ВБ", dataIndex: "commission", key: "commission", width: 90, render: fmtMoney },
  { title: "% комиссии", dataIndex: "commission_pct", key: "commission_pct", width: 80, render: (v: number) => (v * 100).toFixed(1) + "%" },
  { title: "Логистика итого", dataIndex: "logistics_total", key: "logistics_total", width: 100, render: fmtMoney },
  { title: "Лог. на ед.", dataIndex: "logistics_per_unit", key: "logistics_per_unit", width: 90, render: fmtMoney },
  { title: "% лог.", dataIndex: "logistics_pct", key: "logistics_pct", width: 70, render: fmtPct },
  { title: "Прямая лог.", dataIndex: "logistics_direct", key: "logistics_direct", width: 90, render: fmtMoney },
  { title: "Возвратная лог.", dataIndex: "logistics_return", key: "logistics_return", width: 100, render: fmtMoney },
  { title: "Эквайринг+штрафы", dataIndex: "acquiring_penalty", key: "acquiring_penalty", width: 110, render: fmtMoney },
  { title: "Реклама", dataIndex: "ad_spend", key: "ad_spend", width: 90, sorter: (a, b) => a.ad_spend - b.ad_spend, render: fmtMoney },
  { title: "Маржа на ед.", dataIndex: "margin_per_unit", key: "margin_per_unit", width: 100, sorter: (a, b) => a.margin_per_unit - b.margin_per_unit, render: (v: number) => v < 0 ? <span style={{ color: "#ff4d4f" }}>{fmt(v)} \u20BD</span> : fmt(v) + " \u20BD" },
  { title: "Маржа %", dataIndex: "margin_pct", key: "margin_pct", width: 80, sorter: (a, b) => a.margin_pct - b.margin_pct, render: (v: number) => { const s = (v * 100).toFixed(1) + "%"; return v < 0 ? <span style={{ color: "#ff4d4f" }}>{s}</span> : s; } },
  { title: "ROI", dataIndex: "roi", key: "roi", width: 80, sorter: (a, b) => a.roi - b.roi, render: (v: number) => { if (v == null) return "-"; const s = (v * 100).toFixed(1) + "%"; return v < 0 ? <span style={{ color: "#ff4d4f" }}>{s}</span> : <span style={{ color: "#52c41a" }}>{s}</span>; } },
  { title: "Остаток ВБ", dataIndex: "stock_wb", key: "stock_wb", width: 80, render: (v: number) => v > 0 ? v : "-" },
  { title: "В пути", dataIndex: "stock_in_transit", key: "stock_in_transit", width: 70, render: (v: number) => v > 0 ? v : "-" },
  { title: "Запасы дн.", dataIndex: "stock_days", key: "stock_days", width: 80, render: (v: number) => v > 0 ? fmt(v, 1) : "-" },
  { title: "Ср. прод./нед", dataIndex: "avg_sales_per_week", key: "avg_sales_per_week", width: 90, render: (v: number) => v > 0 ? fmt(v, 1) : "-" },
  { title: "Оборач-ть, дн.", dataIndex: "turnover_days", key: "turnover_days", width: 90, render: (v: number) => v > 0 ? fmt(v, 1) : "-" },
];

type PeriodKey = "yesterday" | "7d" | "14d" | "30d" | "month" | "custom";

const PERIOD_OPTIONS = [
  { key: "yesterday" as PeriodKey, label: "Вчера" },
  { key: "7d" as PeriodKey, label: "7 дней" },
  { key: "14d" as PeriodKey, label: "14 дней" },
  { key: "30d" as PeriodKey, label: "30 дней" },
  { key: "month" as PeriodKey, label: "Тек. месяц" },
  { key: "custom" as PeriodKey, label: "Свой" },
];

function getPeriodDates(key: PeriodKey): { date_from: string; date_to: string } {
  const today = dayjs();
  switch (key) {
    case "yesterday": {
      const d = today.subtract(1, "day");
      return { date_from: d.format("YYYY-MM-DD"), date_to: d.format("YYYY-MM-DD") };
    }
    case "7d": return { date_from: today.subtract(7, "day").format("YYYY-MM-DD"), date_to: today.format("YYYY-MM-DD") };
    case "14d": return { date_from: today.subtract(14, "day").format("YYYY-MM-DD"), date_to: today.format("YYYY-MM-DD") };
    case "30d": return { date_from: today.subtract(30, "day").format("YYYY-MM-DD"), date_to: today.format("YYYY-MM-DD") };
    case "month": return { date_from: today.startOf("month").format("YYYY-MM-DD"), date_to: today.format("YYYY-MM-DD") };
    default: return { date_from: "", date_to: "" };
  }
}

const UnitFact: React.FC = () => {
  const [data, setData] = useState<UnitFactRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [periodKey, setPeriodKey] = useState<PeriodKey>("30d");
  const [customRange, setCustomRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  const params = useMemo(() => {
    if (periodKey === "custom" && customRange) {
      return {
        date_from: customRange[0].format("YYYY-MM-DD"),
        date_to: customRange[1].format("YYYY-MM-DD"),
      };
    }
    return getPeriodDates(periodKey);
  }, [periodKey, customRange]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (params.date_from) q.set("date_from", params.date_from);
      if (params.date_to) q.set("date_to", params.date_to);
      const r = await fetch("/api/truestat/unit-fact?" + q.toString());
      const j = await r.json();
      setData(j.data || []);
    } catch (e: any) {
      console.error("UnitFact fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div style={{ padding: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <Title level={4} style={{ margin: 0 }}>ABC, Unit-факт</Title>
        <Space wrap>
          <Radio.Group
            value={periodKey}
            onChange={(e) => setPeriodKey(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            size="small"
          >
            {PERIOD_OPTIONS.map((o) => (
              <Radio.Button key={o.key} value={o.key}>{o.label}</Radio.Button>
            ))}
          </Radio.Group>
          {periodKey === "custom" && (
            <RangePicker
              size="small"
              value={customRange}
              onChange={(v) => {
                if (v && v[0] && v[1]) setCustomRange([v[0], v[1]]);
              }}
            />
          )}
        </Space>
      </div>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <Tag>Товаров: {data.length}</Tag>
          {params.date_from && <Tag color="blue">{params.date_from} → {params.date_to}</Tag>}
          {data.length > 0 && <Tag color="green">Продажи: {data.reduce((s, r) => s + r.sales_count, 0)}</Tag>}
          {data.length > 0 && <Tag color="orange">Выручка: {data.reduce((s, r) => s + r.revenue, 0).toLocaleString("ru-RU")} ₽</Tag>}
        </Space>
      </Card>

      <div style={{ overflowX: "auto" }}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey={(r) => r.vendor_code}
          loading={loading}
          size="small"
          scroll={{ x: 2800 }}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100", "200"] }}
          sticky
        />
      </div>
    </div>
  );
};

export default UnitFact;
