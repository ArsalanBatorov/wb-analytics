import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Input, Space, Card, Row, Col, Statistic, message, Popconfirm, Switch } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, SyncOutlined, SearchOutlined } from '@ant-design/icons';
import { fetchCampaigns, syncCampaigns, startCampaign, pauseCampaign, updateCampaign } from '../api/client';

const statusMap: Record<number, { label: string; color: string }> = {
  4: { label: 'Готова', color: 'blue' },
  7: { label: 'Завершена', color: 'default' },
  8: { label: 'Отказана', color: 'red' },
  9: { label: 'Активна', color: 'green' },
  11: { label: 'На паузе', color: 'orange' },
};

interface Props {
  onOpenCampaign?: (id: number) => void;
}

const Campaigns: React.FC<Props> = ({ onOpenCampaign }) => {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});

  const load = async () => {
    setLoading(true);
    try { setCampaigns(await fetchCampaigns()); } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSync = async () => {
    setLoading(true);
    try {
      await syncCampaigns();
      message.info('Синхронизация запущена');
      setTimeout(load, 8000);
    } catch { message.error('Ошибка синхронизации'); }
    setLoading(false);
  };

  const handleStart = async (wbId: number) => {
    setActionLoading(p => ({ ...p, [wbId]: true }));
    try {
      await startCampaign(wbId);
      message.success(`Кампания ${wbId} запущена`);
      setCampaigns(prev => prev.map(c => c.wb_campaign_id === wbId ? { ...c, status: 9 } : c));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Ошибка запуска');
    }
    setActionLoading(p => ({ ...p, [wbId]: false }));
  };

  const handlePause = async (wbId: number) => {
    setActionLoading(p => ({ ...p, [wbId]: true }));
    try {
      await pauseCampaign(wbId);
      message.success(`Кампания ${wbId} на паузе`);
      setCampaigns(prev => prev.map(c => c.wb_campaign_id === wbId ? { ...c, status: 11 } : c));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Ошибка паузы');
    }
    setActionLoading(p => ({ ...p, [wbId]: false }));
  };

  const handleBidderToggle = async (wbId: number, checked: boolean) => {
    try {
      await updateCampaign(wbId, { is_bidder_active: checked });
      setCampaigns(prev => prev.map(c => c.wb_campaign_id === wbId ? { ...c, is_bidder_active: checked } : c));
    } catch { message.error('Ошибка обновления'); }
  };

  const filtered = campaigns
    .filter(c => filter === null || c.status === filter)
    .filter(c =>
      search === '' ||
      c.name?.toLowerCase().includes(search.toLowerCase()) ||
      String(c.wb_campaign_id).includes(search)
    );

  const counts = {
    all: campaigns.length,
    active: campaigns.filter(c => c.status === 9).length,
    paused: campaigns.filter(c => c.status === 11).length,
    completed: campaigns.filter(c => c.status === 7).length,
    ready: campaigns.filter(c => c.status === 4).length,
    refused: campaigns.filter(c => c.status === 8).length,
  };

  const columns = [
    {
      title: 'ID WB',
      dataIndex: 'wb_campaign_id',
      key: 'wb_campaign_id',
      width: 110,
      render: (id: number) => (
        <a onClick={() => onOpenCampaign?.(id)} style={{ fontWeight: 500 }}>{id}</a>
      ),
    },
    {
      title: 'Название',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (name: string, r: any) => (
        <a onClick={() => onOpenCampaign?.(r.wb_campaign_id)}>{name}</a>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (s: number) => {
        const info = statusMap[s] || { label: `#${s}`, color: 'default' };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: 'Оплата',
      dataIndex: 'payment_type',
      key: 'payment_type',
      width: 80,
      render: (v: string) => v ? v.toUpperCase() : '—',
    },
    {
      title: 'Биддер',
      key: 'bidder',
      width: 80,
      render: (_: any, r: any) => (
        <Switch
          size="small"
          checked={r.is_bidder_active}
          onChange={(checked) => handleBidderToggle(r.wb_campaign_id, checked)}
          disabled={r.status !== 9 && r.status !== 11}
        />
      ),
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 200,
      render: (_: any, r: any) => {
        const wbId = r.wb_campaign_id;
        const isLoading = actionLoading[wbId];
        return (
          <Space size="small">
            {(r.status === 11 || r.status === 4) && (
              <Popconfirm
                title="Запустить кампанию?"
                description={`ID: ${wbId}`}
                onConfirm={() => handleStart(wbId)}
                okText="Да"
                cancelText="Нет"
              >
                <Button
                  type="primary"
                  size="small"
                  icon={<PlayCircleOutlined />}
                  loading={isLoading}
                >
                  Запустить
                </Button>
              </Popconfirm>
            )}
            {r.status === 9 && (
              <Popconfirm
                title="Поставить на паузу?"
                description={`ID: ${wbId}`}
                onConfirm={() => handlePause(wbId)}
                okText="Да"
                cancelText="Нет"
              >
                <Button
                  size="small"
                  icon={<PauseCircleOutlined />}
                  loading={isLoading}
                  danger
                >
                  Пауза
                </Button>
              </Popconfirm>
            )}
            {r.status === 7 && <Tag>Завершена</Tag>}
          </Space>
        );
      },
    },
  ];

  const filterButtons = [
    { key: null, label: 'Все', count: counts.all },
    { key: 9, label: 'Активные', count: counts.active },
    { key: 11, label: 'На паузе', count: counts.paused },
    { key: 4, label: 'Готовые', count: counts.ready },
    { key: 7, label: 'Завершённые', count: counts.completed },
    { key: 8, label: 'Отказанные', count: counts.refused },
  ];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={4}><Card size="small"><Statistic title="Всего" value={counts.all} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Активные" value={counts.active} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="На паузе" value={counts.paused} valueStyle={{ color: '#faad14' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Завершённые" value={counts.completed} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Готовые" value={counts.ready} valueStyle={{ color: '#1890ff' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Отказанные" value={counts.refused} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
      </Row>

      <Space style={{ marginBottom: 16, flexWrap: 'wrap' }} size="small">
        {filterButtons.map(f => (
          <Button
            key={String(f.key)}
            type={filter === f.key ? 'primary' : 'default'}
            size="small"
            onClick={() => setFilter(f.key as number | null)}
          >
            {f.label} ({f.count})
          </Button>
        ))}
        <Input
          placeholder="Поиск по названию или ID"
          prefix={<SearchOutlined />}
          style={{ width: 250 }}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
        />
        <Button icon={<SyncOutlined />} onClick={handleSync} loading={loading}>
          Синхронизировать с WB
        </Button>
      </Space>

      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="wb_campaign_id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 25, showSizeChanger: true, pageSizeOptions: ['25', '50', '100'] }}
        onRow={(record) => ({
          onDoubleClick: () => onOpenCampaign?.(record.wb_campaign_id),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  );
};

export default Campaigns;
