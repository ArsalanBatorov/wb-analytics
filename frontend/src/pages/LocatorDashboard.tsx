import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Spin, Alert, Button, Progress, Typography, Space, Badge } from 'antd';
import { AimOutlined, WarningOutlined, RiseOutlined, ArrowUpOutlined, ArrowDownOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons';
import { fetchLocatorSummary, fetchLocatorDL, fetchLocatorAlerts, fetchLocatorRecommendations } from '../api/client';

const { Title, Text } = Typography;

function DLColor(dl: number): string {
    if (dl >= 60) return 'green';
    if (dl >= 55) return 'orange';
    if (dl >= 50) return 'gold';
    if (dl >= 30) return 'default';
    return 'red';
}

export default function LocatorDashboard() {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState<any>(null);
    const [dlData, setDlData] = useState<any[]>([]);
    const [alerts, setAlerts] = useState<any[]>([]);
    const [recommendations, setRecommendations] = useState<any[]>([]);

    useEffect(() => { loadAll(); }, []);

    async function loadAll() {
        setLoading(true);
        try {
            const [s, d, a] = await Promise.all([
                fetchLocatorSummary(),
                fetchLocatorDL(),
                fetchLocatorAlerts(),
            ]);
            setSummary(s);
            setDlData(d.articles || []);
            setAlerts(a.alerts || []);
        } catch (e) {
            console.error('Locator load error:', e);
        }
        setLoading(false);
    }

    async function loadRecommendations() {
        try {
            const r = await fetchLocatorRecommendations();
            setRecommendations(r.recommendations || []);
        } catch (e) {
            console.error('Recommendations error:', e);
        }
    }

    if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

    const criticalAlerts = alerts.filter(a => a.severity === 'HIGH');
    const mediumAlerts = alerts.filter(a => a.severity === 'MEDIUM');

    // Колонки для основной таблицы
    const mainColumns = [
        { title: 'Артикул', dataIndex: 'vendorCode', key: 'vendorCode', sorter: (a: any, b: any) => a.vendorCode.localeCompare(b.vendorCode), width: 180, fixed: 'left' },
        { title: 'ДЛ, %', dataIndex: 'dl', key: 'dl', sorter: (a: any, b: any) => a.dl - b.dl, render: (dl: number) => <Tag color={DLColor(dl)}>{dl}%</Tag>, width: 90, align: 'center' as const },
        { title: 'Заказы 4 нед', dataIndex: 'orders4w', key: 'orders4w', sorter: (a: any, b: any) => a.orders4w - b.orders4w, width: 110, align: 'right' as const },
        { title: 'Выкуп, %', dataIndex: 'buyoutPercent', key: 'buyoutPercent', sorter: (a: any, b: any) => a.buyoutPercent - b.buyoutPercent, render: (p: number) => `${p}%`, width: 90, align: 'center' as const },
        { title: 'Сток WB', dataIndex: 'totalStock', key: 'totalStock', sorter: (a: any, b: any) => a.totalStock - b.totalStock, width: 90, align: 'right' as const },
        { title: 'OOS через, дн', dataIndex: 'daysToOOS', key: 'daysToOOS', sorter: (a: any, b: any) => a.daysToOOS - b.daysToOOS, render: (d: number) => <Tag color={d < 7 ? 'red' : d < 14 ? 'orange' : d < 30 ? 'gold' : 'green'}>{d === 999 ? '∞' : `${d.toFixed(0)} дн`}</Tag>, width: 110, align: 'center' as const },
        { title: 'Влияние на ИЛ, %', dataIndex: 'ilWeight', key: 'ilWeight', sorter: (a: any, b: any) => a.ilWeight - b.ilWeight, render: (w: number) => <Text>{w?.toFixed(2) ?? '0.00'}%</Text>, width: 120, align: 'right' as const },
    ];

    // Колонки для таблицы размеров (полностью идентичные по ширине и выравниванию)
    const sizeColumns = [
        { title: 'Размер', dataIndex: 'size', key: 'size', width: 180, fixed: 'left' },
        { title: 'ДЛ, %', dataIndex: 'dl', key: 'dl', render: (dl: number) => <Tag color={DLColor(dl)}>{dl}%</Tag>, width: 90, align: 'center' as const },
        { title: 'Заказы 4 нед', dataIndex: 'orders4w', key: 'orders4w', width: 110, align: 'right' as const },
        { title: 'Выкуп, %', dataIndex: 'buyoutPercent', key: 'buyoutPercent', render: (p: number) => `${p}%`, width: 90, align: 'center' as const },
        { title: 'Сток WB', dataIndex: 'stock', key: 'stock', width: 90, align: 'right' as const },
        { title: 'OOS через, дн', dataIndex: 'daysToOOS', key: 'daysToOOS', render: (d: number) => <Tag color={d < 7 ? 'red' : d < 14 ? 'orange' : d < 30 ? 'gold' : 'green'}>{d === 999 ? '∞' : `${d.toFixed(0)} дн`}</Tag>, width: 110, align: 'center' as const },
        { title: 'Влияние на ИЛ, %', dataIndex: 'ilWeight', key: 'ilWeight', render: (w: number) => `${w?.toFixed(2) ?? '0.00'}%`, width: 120, align: 'right' as const },
    ];

    const expandableRow = (record: any) => {
        const sizes = record.sizes || {};
        const sizeData = Object.entries(sizes)
            .map(([size, data]: [string, any]) => ({
                size,
                dl: data.dl,
                orders4w: data.orders4w,
                buyoutPercent: data.buyoutPercent,
                stock: data.stock,
                daysToOOS: data.daysToOOS,
                ilWeight: data.ilWeight,
            }))
            .sort((a, b) => {
                const sizeA = parseInt(a.size);
                const sizeB = parseInt(b.size);
                return sizeA - sizeB;
            });
        if (sizeData.length === 0) return <Text type="secondary">Нет данных по размерам</Text>;
        return (
            <Table
                dataSource={sizeData}
                columns={sizeColumns}
                rowKey="size"
                pagination={false}
                size="small"
                bordered
            />
        );
    };

    return (
        <div style={{ padding: 24 }}>
            <Title level={3}><AimOutlined /> Locator — Контроль локализации</Title>
            <Row gutter={16} style={{ marginBottom: 24 }}>
                <Col span={6}><Card><Statistic title="Индекс Локализации" value={summary?.il ?? '—'} valueStyle={{ color: summary?.il < 1 ? '#3f8600' : '#cf1322' }} prefix={summary?.il < 1 ? <ArrowDownOutlined /> : <ArrowUpOutlined />} suffix={<Text type="secondary">цель &lt;1.0</Text>} /></Card></Col>
                <Col span={6}><Card><Statistic title="Индекс Распределения Продаж" value={summary?.irp ?? '—'} precision={2} valueStyle={{ color: summary?.irp < 0.5 ? '#3f8600' : '#cf1322' }} suffix="%" /><Text type="secondary">цель &lt;0.1% | заказов: {summary?.totalOrders4w}</Text></Card></Col>
                <Col span={6}><Card><Statistic title="Артикулов" value={dlData.length} prefix={<InboxOutlined />} /></Card></Col>
                <Col span={6}><Card><Statistic title="Алертов" value={alerts.length} valueStyle={{ color: criticalAlerts.length > 0 ? '#cf1322' : undefined }} prefix={<WarningOutlined />} suffix={criticalAlerts.length > 0 ? <Tag color="red">{criticalAlerts.length} HIGH</Tag> : null} /></Card></Col>
            </Row>
            {alerts.length > 0 && (
                <Card title={<><WarningOutlined /> Активные алёрты ({alerts.length})</>} style={{ marginBottom: 24 }}>
                    {criticalAlerts.slice(0, 5).map((a, i) => <Alert key={`crit-${i}`} type="error" message={a.message} style={{ marginBottom: 8 }} showIcon />)}
                    {mediumAlerts.slice(0, 5).map((a, i) => <Alert key={`med-${i}`} type="warning" message={a.message} style={{ marginBottom: 8 }} showIcon />)}
                </Card>
            )}
            <Card title="Доля локализации по артикулам" extra={<Button icon={<ReloadOutlined />} onClick={loadAll}>Обновить</Button>} style={{ marginBottom: 24 }}>
                <Table dataSource={dlData} columns={mainColumns} rowKey="vendorCode" expandable={{ expandedRowRender: expandableRow }} pagination={{ pageSize: 15 }} size="small" scroll={{ x: 800 }} />
            </Card>
            <Card title="Рекомендации по поставкам" extra={<Button type="primary" onClick={loadRecommendations}>Рассчитать</Button>}>
                {recommendations.length > 0 ? (
                    <Table dataSource={recommendations} columns={[
                        { title: 'Артикул', dataIndex: 'vendorCode', key: 'vc' },
                        { title: 'Регион', dataIndex: 'region', key: 'region' },
                        { title: 'Потребность', dataIndex: 'need', key: 'need', sorter: (a: any, b: any) => a.need - b.need },
                        { title: 'Текущий сток', dataIndex: 'currentStock', key: 'stock', sorter: (a: any, b: any) => a.currentStock - b.currentStock },
                        { title: 'Коробок', dataIndex: 'boxesSuggested', key: 'boxes', render: (v: number) => <Tag color="blue">{v} кор</Tag> },
                        { title: 'Приоритет', dataIndex: 'priorityScore', key: 'prio', render: (s: number) => <Progress percent={Math.min(s, 100)} size="small" status={s >= 80 ? 'exception' : s >= 50 ? 'active' : 'normal'} /> },
                    ]} rowKey={(r: any) => `${r.vendorCode}-${r.region}`} pagination={{ pageSize: 10 }} size="small" />
                ) : <Text type="secondary">Нажмите «Рассчитать» для получения рекомендаций</Text>}
            </Card>
        </div>
    );
}
