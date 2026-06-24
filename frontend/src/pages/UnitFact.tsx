import React, { useEffect, useState } from "react";
import {
  Table, Card, Button, Upload, message, Tag, Space, Typography,
} from "antd";
import { UploadOutlined, ReloadOutlined, CloudSyncOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";

const { Title } = Typography;

interface UnitFactRow {
  id: number;
  manager: string;
  vendor_code: string;
  size: string;
  row_type: string;
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
  orders_4w: number;
  sales_4w: number;
  buyout_4w_pct: number;
  orders_18w: number;
  sales_18w: number;
  buyout_18w_pct: number;
  stock_wb: number;
  stock_in_transit: number;
  stock_days: number;
  stock_wb_prev: number;
  avg_sales_per_week: number;
  turnover_days: number;
}

const fmt = (v: number | null | undefined, digits = 2): string => {
  if (v == null) return "-";
  if (typeof v !== "number") return String(v);
  return v.toLocaleString("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const fmtPct = (v: number | null | undefined): string => {
  if (v == null) return "-";
  return (v * 100).toFixed(1) + "%";
};

const fmtMoney = (v: number | null | undefined): string => {
  if (v == null || v === 0) return "-";
  return fmt(v) + " ₽";
};

const columns: ColumnsType<UnitFactRow> = [
  {
    title: "Артикул",
    dataIndex: "vendor_code",
    key: "vendor_code",
    width: 140,
    fixed: "left",
    render: (v: string, r: UnitFactRow) => {
      if (r.row_type === "vendor_total") return <strong>{v}</strong>;
      if (r.row_type === "grand_total") return <strong style={{ fontSize: 14 }}>Итого</strong>;
      return v;
    },
    onCell: (r: UnitFactRow) => ({
      style: {
        fontWeight: r.row_type === "vendor_total" || r.row_type === "grand_total" ? 700 : 400,
        backgroundColor: r.row_type === "grand_total" ? "#f0f0f0" : undefined,
      },
    }),
  },
  { title: "Размер", dataIndex: "size", key: "size", width: 60 },
  {
    title: "Продажи",
    dataIndex: "sales_count",
    key: "sales_count",
    width: 70,
    sorter: (a, b) => a.sales_count - b.sales_count,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Возвраты",
    dataIndex: "returns_count",
    key: "returns_count",
    width: 70,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "% возвр",
    dataIndex: "returns_pct",
    key: "returns_pct",
    width: 70,
    render: fmtPct,
  },
  {
    title: "Орг продажи",
    dataIndex: "net_sales",
    key: "net_sales",
    width: 70,
    sorter: (a, b) => a.net_sales - b.net_sales,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Выручка",
    dataIndex: "revenue",
    key: "revenue",
    width: 100,
    sorter: (a, b) => a.revenue - b.revenue,
    render: fmtMoney,
  },
  {
    title: "Выручка на ед.",
    dataIndex: "revenue_per_unit",
    key: "revenue_per_unit",
    width: 100,
    render: fmtMoney,
  },
  {
    title: "Себестоимость",
    dataIndex: "cost_price_total",
    key: "cost_price_total",
    width: 100,
    sorter: (a, b) => a.cost_price_total - b.cost_price_total,
    render: fmtMoney,
  },
  {
    title: "Себ. на ед.",
    dataIndex: "cost_price_per_unit",
    key: "cost_price_per_unit",
    width: 90,
    render: fmtMoney,
  },
  {
    title: "% себ.",
    dataIndex: "cost_price_pct",
    key: "cost_price_pct",
    width: 70,
    render: fmtPct,
  },
  {
    title: "Комиссия ВБ",
    dataIndex: "commission",
    key: "commission",
    width: 90,
    render: fmtMoney,
  },
  {
    title: "% комиссии",
    dataIndex: "commission_pct",
    key: "commission_pct",
    width: 80,
    render: (v: number) => (v * 100).toFixed(1) + "%",
  },
  {
    title: "Логистика итого",
    dataIndex: "logistics_total",
    key: "logistics_total",
    width: 100,
    render: fmtMoney,
  },
  {
    title: "Лог. на ед.",
    dataIndex: "logistics_per_unit",
    key: "logistics_per_unit",
    width: 90,
    render: fmtMoney,
  },
  {
    title: "% лог.",
    dataIndex: "logistics_pct",
    key: "logistics_pct",
    width: 70,
    render: fmtPct,
  },
  {
    title: "Прямая лог.",
    dataIndex: "logistics_direct",
    key: "logistics_direct",
    width: 90,
    render: fmtMoney,
  },
  {
    title: "Возвратная лог.",
    dataIndex: "logistics_return",
    key: "logistics_return",
    width: 100,
    render: fmtMoney,
  },
  {
    title: "Эквайринг+штрафы",
    dataIndex: "acquiring_penalty",
    key: "acquiring_penalty",
    width: 110,
    render: fmtMoney,
  },
  {
    title: "Реклама",
    dataIndex: "ad_spend",
    key: "ad_spend",
    width: 90,
    sorter: (a, b) => a.ad_spend - b.ad_spend,
    render: fmtMoney,
  },
  {
    title: "Маржа на ед.",
    dataIndex: "margin_per_unit",
    key: "margin_per_unit",
    width: 100,
    sorter: (a, b) => a.margin_per_unit - b.margin_per_unit,
    render: (v: number) => {
      if (v == null) return "-";
      const s = fmt(v) + " ₽";
      return v < 0 ? <span style={{ color: "#ff4d4f" }}>{s}</span> : s;
    },
  },
  {
    title: "Маржа %",
    dataIndex: "margin_pct",
    key: "margin_pct",
    width: 80,
    sorter: (a, b) => a.margin_pct - b.margin_pct,
    render: (v: number) => {
      if (v == null) return "-";
      const s = (v * 100).toFixed(1) + "%";
      return v < 0 ? <span style={{ color: "#ff4d4f" }}>{s}</span> : s;
    },
  },
  {
    title: "ROI",
    dataIndex: "roi",
    key: "roi",
    width: 80,
    sorter: (a, b) => a.roi - b.roi,
    render: (v: number) => {
      if (v == null) return "-";
      const s = (v * 100).toFixed(1) + "%";
      return v < 0 ? <span style={{ color: "#ff4d4f" }}>{s}</span> : <span style={{ color: "#52c41a" }}>{s}</span>;
    },
  },
  {
    title: "Заказы 4н",
    dataIndex: "orders_4w",
    key: "orders_4w",
    width: 80,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Продажи 4н",
    dataIndex: "sales_4w",
    key: "sales_4w",
    width: 80,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Выкуп 4н",
    dataIndex: "buyout_4w_pct",
    key: "buyout_4w_pct",
    width: 70,
    render: fmtPct,
  },
  {
    title: "Заказы 18н",
    dataIndex: "orders_18w",
    key: "orders_18w",
    width: 80,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Продажи 18н",
    dataIndex: "sales_18w",
    key: "sales_18w",
    width: 80,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Выкуп 18н",
    dataIndex: "buyout_18w_pct",
    key: "buyout_18w_pct",
    width: 70,
    render: fmtPct,
  },
  {
    title: "Остаток ВБ",
    dataIndex: "stock_wb",
    key: "stock_wb",
    width: 80,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "В пути",
    dataIndex: "stock_in_transit",
    key: "stock_in_transit",
    width: 70,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Запасы дн.",
    dataIndex: "stock_days",
    key: "stock_days",
    width: 80,
    render: (v: number) => v > 0 ? fmt(v, 1) : "-",
  },
  {
    title: "Остаток пр.нед",
    dataIndex: "stock_wb_prev",
    key: "stock_wb_prev",
    width: 90,
    render: (v: number) => v > 0 ? v : "-",
  },
  {
    title: "Ср. прод./нед",
    dataIndex: "avg_sales_per_week",
    key: "avg_sales_per_week",
    width: 90,
    render: (v: number) => v > 0 ? fmt(v, 1) : "-",
  },
  {
    title: "Оборач-ть, дн.",
    dataIndex: "turnover_days",
    key: "turnover_days",
    width: 90,
    render: (v: number) => v > 0 ? fmt(v, 1) : "-",
  },
];

const UnitFact: React.FC = () => {
  const [data, setData] = useState<UnitFactRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/truestat/unit-fact");
      const j = await r.json();
      setData(j.data || []);
    } catch (e: any) {
      message.error("Ошибка загрузки: " + (e?.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const r = await fetch("/api/truestat/upload-unit-fact", {
        method: "POST",
        body: formData,
      });
      const result = await r.json();
      if (result.status === "ok") {
        message.success(`Загружено ${result.imported} строк`);
        await fetchData();
      } else {
        message.error("Ошибка: " + JSON.stringify(result));
      }
    } catch (e: any) {
      message.error("Ошибка загрузки: " + (e?.message ?? e));
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleRefreshFromApi = async () => {
    setRefreshing(true);
    try {
      const r = await fetch("/api/truestat/refresh-unit-fact", { method: "POST" });
      const result = await r.json();
      if (result.status === "ok") {
        message.success(`Рассчитано ${result.imported} товаров`);
        await fetchData();
      } else {
        message.error("Ошибка: " + JSON.stringify(result));
      }
    } catch (e: any) {
      message.error("Ошибка: " + (e?.message ?? e));
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div style={{ padding: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Title level={4} style={{ margin: 0 }}>ABC, Unit-факт</Title>
        <Space>
          <Button icon={<CloudSyncOutlined />} onClick={handleRefreshFromApi} loading={refreshing}>
            Из данных сервера
          </Button>
          <Upload accept=".xlsx" showUploadList={false} beforeUpload={handleUpload} disabled={uploading}>
            <Button icon={<UploadOutlined />} loading={uploading}>
              Загрузить XLSX
            </Button>
          </Upload>
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            Обновить
          </Button>
        </Space>
      </div>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <Tag>Всего строк: {data.length}</Tag>
          <Tag color="blue">Детальные: {data.filter(r => r.row_type === "detail").length}</Tag>
          <Tag color="green">По артикулам: {data.filter(r => r.row_type === "vendor_total").length}</Tag>
        </Space>
      </Card>

      <div style={{ overflowX: "auto" }}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          size="small"
          scroll={{ x: 3200 }}
          pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["20", "50", "100", "200"] }}
          sticky
        />
      </div>
    </div>
  );
};

export default UnitFact;
