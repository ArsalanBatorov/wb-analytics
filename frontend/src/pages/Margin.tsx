/**
 * Страница «План/Факт» — фактическая маржа кассовым методом.
 *
 * Источник: GET /margin/{summary,daily,products}.
 * Поля выручки на бэкенде называются sales_revenue (не revenue) — учитываем.
 * Поля артикула и названия: vendor_code, title (из join с таблицей products).
 */
import { useEffect, useState, useMemo } from "react";
import {
  Card, Row, Col, DatePicker, Radio, Table, Spin, Statistic, Typography, Space,
} from "antd";
import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from "recharts";
import dayjs, { Dayjs } from "dayjs";
import {
  fetchMarginSummary, fetchMarginDaily, fetchMarginProducts,
} from "../api/client";

const { RangePicker } = DatePicker;
const { Title } = Typography;

// --- утилиты форматирования ---
const fmt   = (n: number) => (n ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
const fmtR  = (n: number) => fmt(n) + " ₽";
const fmtP  = (n: number) => (n ?? 0).toFixed(1) + " %";

export default function Margin() {
  // preset: 1 = вчера, 7/14/30 = последние N дней, "month" = текущий месяц, "custom" = свой
  const [preset, setPreset] = useState<number | "month" | "custom">(30);
  const [range, setRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(29, "day"), dayjs(),
  ]);

  const [dateFrom, dateTo] = useMemo(() => {
    if (preset === "custom") return [range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD")];
    if (preset === "month")  return [dayjs().startOf("month").format("YYYY-MM-DD"), dayjs().format("YYYY-MM-DD")];
    if (preset === 1) {
      const y = dayjs().subtract(1, "day").format("YYYY-MM-DD");
      return [y, y];
    }
    return [dayjs().subtract((preset as number) - 1, "day").format("YYYY-MM-DD"),
            dayjs().format("YYYY-MM-DD")];
  }, [preset, range]);

  const [summary, setSummary]   = useState<any>(null);
  const [daily, setDaily]       = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading]   = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchMarginSummary({ date_from: dateFrom, date_to: dateTo }),
      fetchMarginDaily({ date_from: dateFrom, date_to: dateTo }),
      fetchMarginProducts({ date_from: dateFrom, date_to: dateTo }),
    ])
      .then(([s, d, p]: any[]) => {
        // /summary возвращает { summary: {...} } — разворачиваем
        setSummary(s?.summary ?? s);
        // /daily возвращает { rows: [...] } или { items: [...] }
        setDaily(d?.rows ?? d?.items ?? d ?? []);
        // /products возвращает { products: [...] }
        setProducts(p?.products ?? p?.items ?? []);
      })
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  const chartData = useMemo(() => {
    return (daily ?? []).map((d: any) => ({
      date: dayjs(d.date ?? d.stat_date).format("MM-DD"),
      margin: Number(d.margin ?? 0),
    }));
  }, [daily]);

  const columns = [
    {
      title: "Артикул продавца",
      dataIndex: "vendor_code",
      key: "vendor_code",
      width: 160,
      fixed: "left" as const,
      render: (v: string) => v || "—",
    },
    {
      title: "nm_id",
      dataIndex: "nm_id",
      key: "nm_id",
      width: 110,
      render: (v: number) => v
        ? <a href={`https://www.wildberries.ru/catalog/${v}/detail.aspx`} target="_blank" rel="noreferrer">{v}</a>
        : <span style={{ color: "#999" }}>общие</span>,
    },
    { title: "Название", dataIndex: "title", key: "title", ellipsis: true, width: 240,
      render: (v: string) => v || "—" },
    { title: "Продажи", dataIndex: "sales_count", align: "right" as const, width: 90,
      render: (v: number) => fmt(v),
      sorter: (a: any, b: any) => (a.sales_count ?? 0) - (b.sales_count ?? 0) },
    { title: "Возвраты", dataIndex: "returns_count", align: "right" as const, width: 90,
      render: (v: number) => fmt(v),
      sorter: (a: any, b: any) => (a.returns_count ?? 0) - (b.returns_count ?? 0) },
    { title: "Выручка", dataIndex: "sales_revenue", align: "right" as const, width: 120,
      render: (v: number) => fmtR(v),
      sorter: (a: any, b: any) => (a.sales_revenue ?? 0) - (b.sales_revenue ?? 0) },
    { title: "Себестоимость", dataIndex: "cogs", align: "right" as const, width: 130,
      render: (v: number) => fmtR(v),
      sorter: (a: any, b: any) => (a.cogs ?? 0) - (b.cogs ?? 0) },
    { title: "Логистика", dataIndex: "logistics", align: "right" as const, width: 110,
      render: (v: number) => fmtR(v),
      sorter: (a: any, b: any) => (a.logistics ?? 0) - (b.logistics ?? 0) },
    { title: "Реклама", dataIndex: "ad_spend", align: "right" as const, width: 110,
      render: (v: number) => fmtR(v),
      sorter: (a: any, b: any) => (a.ad_spend ?? 0) - (b.ad_spend ?? 0) },
    { title: "Маржа ₽", dataIndex: "margin", align: "right" as const, width: 120,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{fmtR(v)}</span>,
      sorter: (a: any, b: any) => (a.margin ?? 0) - (b.margin ?? 0),
      defaultSortOrder: "ascend" as const },
    { title: "Маржа %", dataIndex: "margin_pct", align: "right" as const, width: 100,
      render: (v: number) => <span style={{ color: v >= 0 ? "#52c41a" : "#ff4d4f" }}>{fmtP(v)}</span>,
      sorter: (a: any, b: any) => (a.margin_pct ?? 0) - (b.margin_pct ?? 0) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={3} style={{ marginTop: 0 }}>План/Факт</Title>

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
        </Space>
      </Card>

      <Spin spinning={loading}>
        {summary && (
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Выручка" value={summary.sales_revenue ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Маржа" value={summary.margin ?? 0}
                formatter={(v) => fmtR(Number(v))}
                valueStyle={{ color: (summary.margin ?? 0) >= 0 ? "#52c41a" : "#ff4d4f" }} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Маржа %" value={summary.margin_pct ?? 0}
                suffix="%" precision={1}
                valueStyle={{ color: (summary.margin_pct ?? 0) >= 0 ? "#52c41a" : "#ff4d4f" }} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Себестоимость" value={summary.cogs ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Логистика" value={summary.logistics ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Реклама" value={summary.ad_spend ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="К перечислению" value={summary.net_payout ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Хранение" value={summary.storage ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Корр. ВВ" value={summary.deduction ?? 0}
                formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Возвраты" value={summary.returns_count ?? 0}
                suffix="шт" /></Card>
            </Col>
          </Row>
        )}

        <Card title="Маржа по дням" style={{ marginBottom: 16 }}>
          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis tickFormatter={(v) => fmt(v)} />
                <Tooltip formatter={(v: number) => fmtR(v)} />
                <ReferenceLine y={0} stroke="#000" />
                <Bar dataKey="margin" name="Маржа ₽">
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.margin >= 0 ? "#52c41a" : "#ff4d4f"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title={`Маржа по SKU (${products.length})`}>
          <Table
            rowKey="nm_id"
            columns={columns as any}
            dataSource={products}
            size="small"
            pagination={{ pageSize: 25, showSizeChanger: true }}
            scroll={{ x: 1400 }}
          />
        </Card>
      </Spin>
    </div>
  );
}
