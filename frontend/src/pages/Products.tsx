import React, { useEffect, useState } from 'react';
import { Table, Select, Button, InputNumber, message, Modal, Tag, Tooltip } from 'antd';
import { ReloadOutlined, EditOutlined } from '@ant-design/icons';
import { fetchProducts, updateCostPrice, updatePlan } from '../api/client';

const fmt = (n: number) => n?.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) || '0';

const Products: React.FC<{ onSelect: (nmId: number) => void }> = ({ onSelect }) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);
  const [editCost, setEditCost] = useState<{ nmId: number; value: number } | null>(null);
  const [editPlan, setEditPlan] = useState<{ nmId: number; value: number } | null>(null);

  const load = () => {
    setLoading(true);
    fetchProducts(days).then(d => setData(d.products || [])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [days]);

  const saveCost = () => {
    if (!editCost) return;
    updateCostPrice(editCost.nmId, editCost.value).then(() => { message.success('Себестоимость сохранена'); setEditCost(null); load(); });
  };
  const savePlan = () => {
    if (!editPlan) return;
    const month = new Date().toISOString().slice(0, 8) + '01';
    updatePlan(editPlan.nmId, month, editPlan.value).then(() => { message.success('План сохранён'); setEditPlan(null); load(); });
  };

  const columns = [
    {
      title: 'Артикул', dataIndex: 'vendor_code', width: 150, fixed: 'left' as const,
      render: (v: string, r: any) => <a onClick={() => onSelect(r.nm_id)}>{v}</a>
    },
    { title: 'Клики', dataIndex: 'clicks', width: 80, sorter: (a: any, b: any) => a.clicks - b.clicks },
    {
      title: 'Заказы (План)', width: 110,
      render: (_: any, r: any) => (
        <span>
          {r.orders} / {r.plan_orders || <Button size="small" type="link" icon={<EditOutlined />} onClick={() => setEditPlan({ nmId: r.nm_id, value: 0 })} />}
        </span>
      ),
      sorter: (a: any, b: any) => a.orders - b.orders
    },
    { title: 'Корзины', dataIndex: 'carts', width: 80, sorter: (a: any, b: any) => a.carts - b.carts },
    { title: 'Заказы ₽', dataIndex: 'revenue', width: 110, render: (v: number) => fmt(v), sorter: (a: any, b: any) => a.revenue - b.revenue },
    { title: 'Цена до СПП', dataIndex: 'price_before_spp', width: 100, render: (v: number) => fmt(v) },
    { title: 'СПП %', dataIndex: 'spp_percent', width: 70, render: (v: number) => v?.toFixed(1) },
    { title: 'Цена после СПП', dataIndex: 'price_after_spp', width: 110, render: (v: number) => fmt(v) },
    {
      title: 'Себест.', dataIndex: 'cost_price', width: 90,
      render: (v: number, r: any) => (
        <span>
          {v > 0 ? fmt(v) : '—'}
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => setEditCost({ nmId: r.nm_id, value: v })} />
        </span>
      )
    },
    { title: 'Комисс+Экв %', dataIndex: 'commission_plus_acquiring_pct', width: 100, render: (v: number) => v?.toFixed(1) },
    { title: 'Комисс+Экв ₽', dataIndex: 'commission_plus_acquiring_rub', width: 100, render: (v: number) => fmt(v) },
    { title: 'Логистика ₽', dataIndex: 'total_logistics', width: 100, render: (v: number) => fmt(v) },
    { title: 'Выкуп %', dataIndex: 'buyout_percent', width: 80, render: (v: number) => v?.toFixed(1) },
    { title: 'Лог. до клиента', dataIndex: 'delivery_to_client', width: 110, render: (v: number) => fmt(v) },
    { title: 'Обр. логистика', dataIndex: 'return_delivery', width: 110, render: (v: number) => fmt(v) },
    { title: 'МП до нал. %', dataIndex: 'mp_before_tax_pct', width: 100, render: (v: number) => <span style={{ color: v > 0 ? '#3f8600' : '#cf1322' }}>{v?.toFixed(1)}%</span> },
    { title: 'МП до нал. ₽', dataIndex: 'mp_before_tax_rub', width: 100, render: (v: number) => fmt(v) },
    { title: 'Налог ₽', dataIndex: 'tax_rub', width: 80, render: (v: number) => fmt(v) },
    { title: 'НДС ₽', dataIndex: 'vat_rub', width: 80, render: (v: number) => fmt(v) },
    { title: 'МП % (Выкуп)', dataIndex: 'mp_buyout_pct', width: 100, render: (v: number) => v?.toFixed(1) },
    { title: 'МП ₽ (Выкуп)', dataIndex: 'mp_buyout_rub', width: 100, render: (v: number) => fmt(v) },
    { title: 'МП ₽', dataIndex: 'mp_rub', width: 90, render: (v: number) => fmt(v) },
    { title: 'МП с заказа ₽', dataIndex: 'mp_per_order', width: 100, render: (v: number) => fmt(v) },
    { title: 'Хранение ₽', dataIndex: 'storage', width: 90, render: (v: number) => fmt(v) },
    { title: 'Заказы/1000', dataIndex: 'orders_per_1000', width: 90, render: (v: number) => v?.toFixed(2) },
    { title: 'CR Орг.', dataIndex: 'cr_organic', width: 80, render: (v: number) => v?.toFixed(2) + '%' },
    { title: 'CR Рекл.', dataIndex: 'cr_ad', width: 80, render: (v: number) => v?.toFixed(2) + '%' },
    { title: 'Заказы рекл.', dataIndex: 'ad_orders', width: 90 },
    { title: 'Показы рекл.', dataIndex: 'ad_views', width: 100, render: (v: number) => fmt(v) },
    { title: 'CTR рекл. %', dataIndex: 'ad_ctr', width: 90, render: (v: number) => v?.toFixed(2) },
    { title: 'Клики рекл.', dataIndex: 'ad_clicks', width: 90 },
    { title: 'Конв. корзина %', dataIndex: 'conv_to_cart', width: 100, render: (v: number) => v?.toFixed(1) },
    { title: 'Конв. заказ %', dataIndex: 'conv_to_order', width: 100, render: (v: number) => v?.toFixed(1) },
    { title: 'Ср. CPC ₽', dataIndex: 'avg_cpc', width: 90, render: (v: number) => v?.toFixed(2) },
    { title: 'Прибыль/заказ рекл.', dataIndex: 'profit_per_ad_order', width: 130, render: (v: number) => fmt(v) },
    { title: 'CPO рекл.', dataIndex: 'cpo_ad', width: 90, render: (v: number) => fmt(v) },
    { title: 'ДРР %', dataIndex: 'drr', width: 80, render: (v: number) => <span style={{ color: v > 15 ? '#cf1322' : '#3f8600' }}>{v?.toFixed(1)}%</span>, sorter: (a: any, b: any) => a.drr - b.drr },
    { title: 'ДРР чист. %', dataIndex: 'drr_clean', width: 90, render: (v: number) => v?.toFixed(1) },
    { title: 'Рекл. расход ₽', dataIndex: 'ad_spend', width: 100, render: (v: number) => fmt(v), sorter: (a: any, b: any) => a.ad_spend - b.ad_spend },
    { title: 'МП чист. %', dataIndex: 'mp_clean_pct', width: 90, render: (v: number) => <span style={{ color: v > 0 ? '#3f8600' : '#cf1322' }}>{v?.toFixed(1)}%</span> },
    { title: 'МП чист. ₽', dataIndex: 'mp_clean_rub', width: 100, render: (v: number) => fmt(v), sorter: (a: any, b: any) => a.mp_clean_rub - b.mp_clean_rub },
    { title: 'МП чист. орг.', dataIndex: 'mp_clean_organic', width: 100, render: (v: number) => fmt(v) },
    { title: 'МП чист. рекл.', dataIndex: 'mp_clean_ad', width: 100, render: (v: number) => fmt(v) },
    { title: 'ROI %', dataIndex: 'roi', width: 80, render: (v: number) => v?.toFixed(0), sorter: (a: any, b: any) => a.roi - b.roi },
    { title: 'МП чист./заказ', dataIndex: 'mp_clean_per_order', width: 100, render: (v: number) => fmt(v) },
    { title: 'Размеры', dataIndex: 'sizes_available', width: 80 },
    { title: 'Остаток шт.', dataIndex: 'stock', width: 90, sorter: (a: any, b: any) => a.stock - b.stock },
  ];

  // Total row
  const totals = data.reduce((acc, p) => {
    acc.orders += p.orders; acc.revenue += p.revenue; acc.carts += p.carts; acc.clicks += p.clicks;
    acc.ad_spend += p.ad_spend; acc.ad_orders += p.ad_orders; acc.buyouts += p.buyouts;
    acc.mp_clean_rub += p.mp_clean_rub; acc.stock += p.stock;
    return acc;
  }, { orders: 0, revenue: 0, carts: 0, clicks: 0, ad_spend: 0, ad_orders: 0, buyouts: 0, mp_clean_rub: 0, stock: 0 });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Товары ({data.length})</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Tag>Заказы: {fmt(totals.orders)}</Tag>
          <Tag>Выручка: {fmt(totals.revenue)} ₽</Tag>
          <Tag color="green">МП: {fmt(totals.mp_clean_rub)} ₽</Tag>
          <Tag>Рекл: {fmt(totals.ad_spend)} ₽</Tag>
          <Tag>Остаток: {fmt(totals.stock)}</Tag>
          <Select value={days} onChange={setDays} style={{ width: 120 }}
            options={[{ value: 7, label: '7 дней' }, { value: 14, label: '14 дней' }, { value: 30, label: '30 дней' }]} />
          <Button icon={<ReloadOutlined />} onClick={load} />
        </div>
      </div>

      <Table dataSource={data} columns={columns} rowKey="nm_id" loading={loading}
        scroll={{ x: 4000, y: 600 }} size="small" pagination={false}
        onRow={(r) => ({ style: { cursor: 'pointer' } })} />

      <Modal title="Себестоимость" open={!!editCost} onOk={saveCost} onCancel={() => setEditCost(null)}>
        <InputNumber value={editCost?.value} onChange={(v) => setEditCost(prev => prev ? { ...prev, value: v || 0 } : null)}
          style={{ width: '100%' }} addonAfter="₽" min={0} />
      </Modal>
      <Modal title="План заказов (месяц)" open={!!editPlan} onOk={savePlan} onCancel={() => setEditPlan(null)}>
        <InputNumber value={editPlan?.value} onChange={(v) => setEditPlan(prev => prev ? { ...prev, value: v || 0 } : null)}
          style={{ width: '100%' }} addonAfter="шт" min={0} />
      </Modal>
    </div>
  );
};
export default Products;
