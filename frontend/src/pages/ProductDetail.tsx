import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Button, Spin, Descriptions } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { fetchProductDaily, fetchProducts } from '../api/client';

const fmt = (n: number) => n?.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) || '0';

const ProductDetail: React.FC<{ nmId: number; onBack: () => void }> = ({ nmId, onBack }) => {
  const [daily, setDaily] = useState<any>(null);
  const [product, setProduct] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchProductDaily(nmId, 7),
      fetchProducts(7).then(d => d.products?.find((p: any) => p.nm_id === nmId))
    ]).then(([d, p]) => { setDaily(d); setProduct(p); }).finally(() => setLoading(false));
  }, [nmId]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const p = product || {};
  const days = daily?.daily || [];

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={onBack} style={{ marginBottom: 16 }}>Назад</Button>
      <h2>{p.vendor_code} — {p.title}</h2>

      <Row gutter={[16, 16]}>
        <Col span={4}><Card><Statistic title="Заказы" value={p.orders} /></Card></Col>
        <Col span={4}><Card><Statistic title="Выручка" value={p.revenue} formatter={v => fmt(Number(v))} /></Card></Col>
        <Col span={4}><Card><Statistic title="МП чист." value={p.mp_clean_rub} formatter={v => fmt(Number(v))} valueStyle={{ color: p.mp_clean_rub > 0 ? '#3f8600' : '#cf1322' }} /></Card></Col>
        <Col span={4}><Card><Statistic title="ДРР" value={p.drr} precision={1} suffix="%" /></Card></Col>
        <Col span={4}><Card><Statistic title="Рекл. расход" value={p.ad_spend} formatter={v => fmt(Number(v))} /></Card></Col>
        <Col span={4}><Card><Statistic title="Остаток" value={p.stock} /></Card></Col>
      </Row>

      <Card title="Заказы по дням (факт vs план)" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={days}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={(v) => v.slice(5)} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="orders" stroke="#1677ff" name="Заказы факт" strokeWidth={2} />
            <Line type="monotone" dataKey="daily_plan" stroke="#ff4d4f" name="План/день" strokeDasharray="5 5" />
            <Line type="monotone" dataKey="cumulative_orders" stroke="#52c41a" name="Накоп. факт" strokeWidth={2} />
            <Line type="monotone" dataKey="cumulative_plan" stroke="#faad14" name="Накоп. план" strokeDasharray="5 5" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Выручка и рекл. расход по дням" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={days}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={(v) => v.slice(5)} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="revenue" fill="#1677ff" name="Выручка" />
            <Bar dataKey="ad_spend" fill="#ff4d4f" name="Рекл. расход" />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
};
export default ProductDetail;
