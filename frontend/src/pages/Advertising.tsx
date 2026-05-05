/**
 * Страница «Реклама» — рекламная аналитика по магазину и по SKU.
 *
 * Источники:
 *   - GET /analytics/advertising-summary — общая сводка (расход, ДРР, CTR, CPC, CPO, заказы)
 *   - GET /analytics/advertising-products — таблица по SKU (показы, клики, расход, CPO, ДРР)
 *
 * CPO считается на бэкенде как: расход_по_SKU / ВСЕ заказы по SKU (включая органику),
 * а не только из рекламы — это честная экономика SKU.
 */
import { useEffect, useMemo, useState } from "react";
import {
  Card, Row, Col, DatePicker, Radio, Table, Spin, Statistic, Typography, Tag, Space, Input,
} from "antd";
import dayjs, { Dayjs } from "dayjs";
import {
  fetchAdvertisingSummary, fetchAdvertisingProducts,
  makePeriod, makeCustomPeriod, type Period,
} from "../api/client";

const { RangePicker } = DatePicker;
const { Title } = Typography;

// --- утилиты форматирования ---
const fmt  = (n: number) => (n ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
const fmtR = (n: number) => fmt(n) + " ₽";
const fmtP = (n: number) => (n ?? 0).toFixed(2) + " %";

// Тип ответа /advertising-summary
type AdvSummary = {
  date_from: string; date_to: string;
  views: number; clicks: number; ctr: number; cpm: number; cpc: number;
  spend: number; add_to_cart: number; ad_orders: number;
  total_orders: number; total_order_sum: number;
  revenue: number; cpo: number; drr: number;
};

// Тип строки таблицы /advertising-products
type AdvProduct = {
  nm_id: number; vendor_code: string; title: string; brand: string;
  views: number; clicks: number; ctr: number; cpm: number; cpc: number;
  spend: number; atc: number; ad_orders: number;
  total_orders: number; total_order_sum: number;
  revenue: number; cpo: number; drr: number;
};

export default function Advertising() {
  // --- состояние периода ---
  const [preset, setPreset] = useState<number | "custom">(7);
  const [range, setRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(6, "day"), dayjs(),
  ]);

  const period: Period = useMemo(() => {
    if (preset === "custom") {
      return makeCustomPeriod(range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD"));
    }
    return makePeriod(preset);
  }, [preset, range]);

  // --- данные ---
  const [summary, setSummary]   = useState<AdvSummary | null>(null);
  const [products, setProducts] = useState<AdvProduct[]>([]);
  const [loading, setLoading]   = useState(false);
  const [search, setSearch]     = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchAdvertisingSummary(period),
      fetchAdvertisingProducts(period),
    ])
      .then(([s, p]) => {
        setSummary(s);
        setProducts(p?.items ?? []);
      })
      .finally(() => setLoading(false));
  }, [period]);

  // --- фильтр по поиску (nm_id / артикул / название) ---
  const filtered = useMemo(() => {
    if (!search.trim()) return products;
    const q = search.toLowerCase();
    return products.filter(p =>
      String(p.nm_id).includes(q) ||
      (p.vendor_code ?? "").toLowerCase().includes(q) ||
      (p.title ?? "").toLowerCase().includes(q)
    );
  }, [products, search]);

  // --- колонки таблицы ---
  const columns = [
    {
      title: "SKU", dataIndex: "nm_id", width: 110, fixed: "left" as const,
      render: (v: number, r: AdvProduct) => (
        <a href={`https://www.wildberries.ru/catalog/${v}/detail.aspx`} target="_blank" rel="noreferrer">
          {v}
        </a>
      ),
    },
    {
      title: "Артикул", dataIndex: "vendor_code", width: 140, ellipsis: true,
    },
    {
      title: "Название", dataIndex: "title", ellipsis: true, width: 240,
    },
    { title: "Показы",  dataIndex: "views",    width: 90,  align: "right" as const, render: fmt,
      sorter: (a: AdvProduct, b: AdvProduct) => a.views - b.views },
    { title: "Клики",   dataIndex: "clicks",   width: 80,  align: "right" as const, render: fmt,
      sorter: (a: AdvProduct, b: AdvProduct) => a.clicks - b.clicks },
    { title: "CTR",     dataIndex: "ctr",      width: 80,  align: "right" as const, render: fmtP,
      sorter: (a: AdvProduct, b: AdvProduct) => a.ctr - b.ctr },
    { title: "CPC",     dataIndex: "cpc",      width: 90,  align: "right" as const, render: fmtR,
      sorter: (a: AdvProduct, b: AdvProduct) => a.cpc - b.cpc },
    { title: "Расход",  dataIndex: "spend",    width: 110, align: "right" as const, render: fmtR,
      sorter: (a: AdvProduct, b: AdvProduct) => a.spend - b.spend, defaultSortOrder: "descend" as const },
    { title: "Заказы (всего)", dataIndex: "total_orders", width: 110, align: "right" as const, render: fmt,
      sorter: (a: AdvProduct, b: AdvProduct) => a.total_orders - b.total_orders },
    {
      title: "CPO", dataIndex: "cpo", width: 100, align: "right" as const,
      render: (v: number, r: AdvProduct) => {
        // подсветка: CPO без заказов = слив бюджета (красный)
        if (r.total_orders === 0 && r.spend > 0) return <Tag color="red">слив</Tag>;
        if (v === 0) return "—";
        return fmtR(v);
      },
      sorter: (a: AdvProduct, b: AdvProduct) => a.cpo - b.cpo,
    },
    { title: "Выручка SKU", dataIndex: "revenue", width: 120, align: "right" as const, render: fmtR,
      sorter: (a: AdvProduct, b: AdvProduct) => a.revenue - b.revenue },
    {
      title: "ДРР", dataIndex: "drr", width: 90, align: "right" as const,
      render: (v: number) => {
        // зелёный <10%, жёлтый 10-20%, красный >20%
        const color = v < 10 ? "green" : v < 20 ? "orange" : "red";
        return <Tag color={color}>{v.toFixed(2)} %</Tag>;
      },
      sorter: (a: AdvProduct, b: AdvProduct) => a.drr - b.drr,
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={3} style={{ marginTop: 0 }}>Реклама</Title>

      {/* === Селектор периода === */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Radio.Group value={preset} onChange={e => setPreset(e.target.value)}>
            <Radio.Button value={7}>7 дней</Radio.Button>
            <Radio.Button value={14}>14 дней</Radio.Button>
            <Radio.Button value={30}>30 дней</Radio.Button>
            <Radio.Button value="custom">Свой</Radio.Button>
          </Radio.Group>
          {preset === "custom" && (
            <RangePicker value={range} onChange={(v) => v && setRange(v as [Dayjs, Dayjs])} />
          )}
        </Space>
      </Card>

      <Spin spinning={loading}>
        {/* === KPI-карточки === */}
        {summary && (
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Расход" value={summary.spend} formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="ДРР общий" value={summary.drr} suffix="%"
                valueStyle={{ color: summary.drr < 10 ? "#52c41a" : summary.drr < 20 ? "#faad14" : "#ff4d4f" }} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Показы" value={summary.views} formatter={(v) => fmt(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Клики" value={summary.clicks} formatter={(v) => fmt(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="CTR" value={summary.ctr} suffix="%" precision={2} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="CPC" value={summary.cpc} formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="CPO" value={summary.cpo} formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Заказы (всего)" value={summary.total_orders} formatter={(v) => fmt(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Заказы из рекл." value={summary.ad_orders} formatter={(v) => fmt(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Выручка" value={summary.revenue} formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
            <Col xs={12} md={6} lg={4}>
              <Card><Statistic title="Сумма всех заказов" value={summary.total_order_sum} formatter={(v) => fmtR(Number(v))} /></Card>
            </Col>
          </Row>
        )}

        {/* === Таблица по SKU === */}
        <Card
          title={`Реклама по SKU (${filtered.length})`}
          extra={
            <Input.Search
              allowClear placeholder="nm_id / артикул / название" style={{ width: 280 }}
              onChange={e => setSearch(e.target.value)}
            />
          }
        >
          <Table
            rowKey="nm_id"
            columns={columns as any}
            dataSource={filtered}
            size="small"
            pagination={{ pageSize: 25, showSizeChanger: true }}
            scroll={{ x: 1500 }}
          />
        </Card>
      </Spin>
    </div>
  );
}
