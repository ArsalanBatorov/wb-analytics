import React, { useEffect, useState, useCallback } from 'react';
import { Table, Button, Card, Tabs, Badge, Tag, Space, Statistic, Row, Col, InputNumber, Modal, message, Popconfirm, Input } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, DeleteOutlined, MinusCircleOutlined, SearchOutlined } from '@ant-design/icons';
import api from '../api/client';

interface Props {
  campaignId: number;
  onBack: () => void;
}

interface ClusterRow {
  key: string;
  id: number;
  norm_query: string;
  views: number;
  clicks: number;
  spend: number;
  ctr: number;
  cpm: number;
}

interface FullStats {
  atbs: number;
  orders: number;
  clicks: number;
  views: number;
  sum: number;
  cr: number;
}

interface MinusPhrase {
  phrase: string;
  views: number;
  clicks: number;
  spend: number;
  ctr: number;
}

const Campaign: React.FC<Props> = ({ campaignId, onBack }) => {
  const [clusters, setClusters] = useState<any[]>([]);
  const [keywordStats, setKeywordStats] = useState<Record<string, any>>({});
  const [fullStats, setFullStats] = useState<FullStats>({ atbs: 0, orders: 0, clicks: 0, views: 0, sum: 0, cr: 0 });
  const [minusPhrases, setMinusPhrases] = useState<string[]>([]);
  const [minusCount, setMinusCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [minusLoading, setMinusLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [sendingMinus, setSendingMinus] = useState(false);
  const [nmId, setNmId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState('clusters');
  const [searchText, setSearchText] = useState('');
  const [minusSearchText, setMinusSearchText] = useState('');
  const [editingCpm, setEditingCpm] = useState<Record<string, number>>({});
  const [savingCpm, setSavingCpm] = useState<string | null>(null);
  const [uniformCpmModal, setUniformCpmModal] = useState(false);
  const [uniformCpmValue, setUniformCpmValue] = useState<number>(200);

  const loadClusters = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get(`/clusters/${campaignId}`);
      const data = resp.data || [];
      setClusters(data);
      if (data.length > 0 && data[0].nm_id) {
        setNmId(data[0].nm_id);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [campaignId]);

  const loadKeywordStats = useCallback(async () => {
    try {
      const resp = await api.get(`/clusters/keyword-stats/${campaignId}`);
      const map: Record<string, any> = {};
      for (const kw of (resp.data?.keywords || [])) {
        map[kw.keyword] = kw;
      }
      setKeywordStats(map);
    } catch (e) { console.error(e); }
  }, [campaignId]);

  const loadFullStats = useCallback(async () => {
    try {
      const resp = await api.get(`/clusters/fullstats/${campaignId}`);
      setFullStats(resp.data || { atbs: 0, orders: 0, clicks: 0, views: 0, sum: 0, cr: 0 });
    } catch (e) { console.error(e); }
  }, [campaignId]);

  const loadMinusPhrases = useCallback(async () => {
    if (!nmId) return;
    setMinusLoading(true);
    try {
      const resp = await api.get(`/minus/wb/${campaignId}/${nmId}`);
      setMinusPhrases(resp.data?.phrases || []);
      setMinusCount(resp.data?.count || 0);
    } catch (e) { console.error(e); }
    setMinusLoading(false);
  }, [campaignId, nmId]);

  useEffect(() => { loadClusters(); loadKeywordStats(); loadFullStats(); }, [loadClusters, loadKeywordStats, loadFullStats]);
  useEffect(() => { if (nmId) loadMinusPhrases(); }, [nmId, loadMinusPhrases]);

  const clusterRows: ClusterRow[] = clusters.map((c) => {
    const kw = keywordStats[c.norm_query] || {};
    return {
      key: String(c.id),
      id: c.id,
      norm_query: c.norm_query,
      views: kw.views || c.views || 0,
      clicks: kw.clicks || c.clicks || 0,
      spend: kw.sum || c.spend || 0,
      ctr: kw.ctr || c.ctr || 0,
      cpm: c.cpm || 0,
    };
  });

  const filteredClusters = clusterRows.filter(c =>
    !searchText || c.norm_query.toLowerCase().includes(searchText.toLowerCase())
  );

  const minusRows: MinusPhrase[] = minusPhrases.map((phrase) => {
    const kw = keywordStats[phrase] || {};
    return { phrase, views: kw.views || 0, clicks: kw.clicks || 0, spend: kw.sum || 0, ctr: kw.ctr || 0 };
  });

  const filteredMinus = minusRows.filter(m =>
    !minusSearchText || m.phrase.toLowerCase().includes(minusSearchText.toLowerCase())
  );

  const handleSendToMinus = async () => {
    if (!nmId || selectedRowKeys.length === 0) return;
    setSendingMinus(true);
    try {
      const phrases = clusterRows.filter(c => selectedRowKeys.includes(c.key)).map(c => c.norm_query);
      await api.post('/minus/instant', { campaign_id: campaignId, nm_id: nmId, phrases, reason: 'manual' });
      message.success(`Отправлено ${phrases.length} фраз в минус`);
      setSelectedRowKeys([]);
      loadMinusPhrases();
    } catch (e) { message.error('Ошибка'); }
    setSendingMinus(false);
  };

  const handleRemoveFromMinus = async (phrase: string) => {
    if (!nmId) return;
    try {
      await api.post('/minus/remove', { campaign_id: campaignId, nm_id: nmId, phrases: [phrase] });
      message.success('Удалено');
      loadMinusPhrases();
    } catch (e) { message.error('Ошибка'); }
  };

  const handleSaveCpm = async (normQuery: string) => {
    if (!nmId) return;
    const cpm = editingCpm[normQuery];
    if (cpm === undefined) return;
    setSavingCpm(normQuery);
    try {
      await api.post('/clusters/set-cpm', { campaign_id: campaignId, nm_id: nmId, bids: [{ norm_query: normQuery, cpm }] });
      message.success(`CPM ${cpm} установлен`);
      setEditingCpm(prev => { const n = { ...prev }; delete n[normQuery]; return n; });
      loadClusters();
    } catch (e) { message.error('Ошибка'); }
    setSavingCpm(null);
  };

  const handleUniformCpm = async () => {
    if (!nmId) return;
    try {
      const queries = selectedRowKeys.length > 0
        ? clusterRows.filter(c => selectedRowKeys.includes(c.key)).map(c => c.norm_query)
        : clusterRows.map(c => c.norm_query);
      await api.post('/clusters/set-uniform-cpm', { campaign_id: campaignId, nm_id: nmId, cpm: uniformCpmValue, norm_queries: queries });
      message.success(`CPM ${uniformCpmValue} для ${queries.length} фраз`);
      setUniformCpmModal(false);
      setSelectedRowKeys([]);
      loadClusters();
    } catch (e) { message.error('Ошибка'); }
  };

  const clusterColumns = [
    { title: 'Ключевая фраза', dataIndex: 'norm_query', key: 'norm_query', sorter: (a: ClusterRow, b: ClusterRow) => a.norm_query.localeCompare(b.norm_query) },
    { title: 'Показы', dataIndex: 'views', key: 'views', sorter: (a: ClusterRow, b: ClusterRow) => a.views - b.views, width: 100 },
    { title: 'Клики', dataIndex: 'clicks', key: 'clicks', sorter: (a: ClusterRow, b: ClusterRow) => a.clicks - b.clicks, width: 90 },
    { title: 'Расход, ₽', dataIndex: 'spend', key: 'spend', render: (v: number) => v.toFixed(2), sorter: (a: ClusterRow, b: ClusterRow) => a.spend - b.spend, width: 110 },
    { title: 'CTR, %', dataIndex: 'ctr', key: 'ctr', render: (v: number) => v.toFixed(2), sorter: (a: ClusterRow, b: ClusterRow) => a.ctr - b.ctr, width: 90 },
    {
      title: 'CPM', dataIndex: 'cpm', key: 'cpm', width: 140,
      sorter: (a: ClusterRow, b: ClusterRow) => a.cpm - b.cpm,
      render: (val: number, record: ClusterRow) => {
        const isEditing = editingCpm[record.norm_query] !== undefined;
        return (
          <Space size={4}>
            <InputNumber size="small" min={0} step={10} value={isEditing ? editingCpm[record.norm_query] : val}
              onChange={(v) => setEditingCpm(prev => ({ ...prev, [record.norm_query]: v || 0 }))} style={{ width: 80 }} />
            {isEditing && <Button size="small" type="primary" loading={savingCpm === record.norm_query} onClick={() => handleSaveCpm(record.norm_query)}>✓</Button>}
          </Space>
        );
      },
    },
  ];

  const minusColumns = [
    { title: 'Фраза', dataIndex: 'phrase', key: 'phrase', sorter: (a: MinusPhrase, b: MinusPhrase) => a.phrase.localeCompare(b.phrase) },
    { title: 'Показы', dataIndex: 'views', key: 'views', sorter: (a: MinusPhrase, b: MinusPhrase) => a.views - b.views, width: 100 },
    { title: 'Клики', dataIndex: 'clicks', key: 'clicks', sorter: (a: MinusPhrase, b: MinusPhrase) => a.clicks - b.clicks, width: 90 },
    { title: 'Расход, ₽', dataIndex: 'spend', key: 'spend', render: (v: number) => v.toFixed(2), sorter: (a: MinusPhrase, b: MinusPhrase) => a.spend - b.spend, width: 110 },
    { title: 'CTR, %', dataIndex: 'ctr', key: 'ctr', render: (v: number) => v.toFixed(2), sorter: (a: MinusPhrase, b: MinusPhrase) => a.ctr - b.ctr, width: 90 },
    {
      title: '', key: 'action', width: 50,
      render: (_: any, record: MinusPhrase) => (
        <Popconfirm title="Удалить из минуса?" onConfirm={() => handleRemoveFromMinus(record.phrase)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack}>Назад</Button>
        <Button icon={<ReloadOutlined />} onClick={() => { loadClusters(); loadKeywordStats(); loadFullStats(); loadMinusPhrases(); }}>Обновить</Button>
      </Space>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}><Card size="small"><Statistic title="Показы" value={fullStats.views} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Клики" value={fullStats.clicks} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Расход" value={fullStats.sum} precision={2} suffix="₽" /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Корзина" value={fullStats.atbs} valueStyle={{ color: '#cf1322' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="Заказы" value={fullStats.orders} valueStyle={{ color: '#3f8600' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="CR, %" value={fullStats.cr} precision={2} suffix="%" /></Card></Col>
      </Row>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: 'clusters',
          label: `Кластеры (${clusters.length})`,
          children: (
            <>
              <Space style={{ marginBottom: 12 }}>
                <Input placeholder="Поиск..." prefix={<SearchOutlined />} value={searchText} onChange={e => setSearchText(e.target.value)} style={{ width: 300 }} allowClear />
                {selectedRowKeys.length > 0 && (
                  <Button danger type="primary" icon={<MinusCircleOutlined />} loading={sendingMinus} onClick={handleSendToMinus}>
                    В минус ({selectedRowKeys.length})
                  </Button>
                )}
                <Button onClick={() => setUniformCpmModal(true)}>Единый CPM {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : '(все)'}</Button>
              </Space>
              <Table rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
                columns={clusterColumns} dataSource={filteredClusters} loading={loading} size="small"
                pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `Всего: ${t}` }} scroll={{ y: 600 }} />
            </>
          ),
        },
        {
          key: 'minus',
          label: <Badge count={minusCount} offset={[15, 0]} size="small"><span>Минус-фразы</span></Badge>,
          children: (
            <>
              <Space style={{ marginBottom: 12 }}>
                <Input placeholder="Поиск..." prefix={<SearchOutlined />} value={minusSearchText} onChange={e => setMinusSearchText(e.target.value)} style={{ width: 300 }} allowClear />
                <Tag color="red">{minusCount} фраз</Tag>
              </Space>
              <Table columns={minusColumns} dataSource={filteredMinus} rowKey="phrase" loading={minusLoading} size="small"
                pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `Всего: ${t}` }} scroll={{ y: 600 }} />
            </>
          ),
        },
      ]} />

      <Modal title="Единый CPM" open={uniformCpmModal} onOk={handleUniformCpm} onCancel={() => setUniformCpmModal(false)}>
        <p>Для {selectedRowKeys.length > 0 ? `${selectedRowKeys.length} выбранных` : `всех ${clusters.length}`} фраз</p>
        <InputNumber min={0} step={10} value={uniformCpmValue} onChange={(v) => setUniformCpmValue(v || 0)} style={{ width: '100%' }} addonAfter="₽" />
      </Modal>
    </div>
  );
};

export default Campaign;
