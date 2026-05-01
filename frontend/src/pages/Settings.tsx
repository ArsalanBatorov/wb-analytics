import React, { useEffect, useState } from 'react';
import { Card, Form, Input, InputNumber, Button, message, Descriptions, Tag, Divider } from 'antd';
import { fetchSettings, updateSettings } from '../api/client';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [form] = Form.useForm();

  const load = () => {
    setLoading(true);
    fetchSettings().then(d => { setSettings(d); form.setFieldsValue({
      tax_rate: d.tax_rate?.value || '6',
      vat_rate: d.vat_rate?.value || '0',
      ktr_value: d.ktr_value?.value || '',
      irp_value: d.irp_value?.value || '',
      wb_api_token: d.wb_api_token?.value || '',
    }); }).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const save = (values: any) => {
    updateSettings(values).then(() => { message.success('Настройки сохранены'); load(); });
  };

  return (
    <div>
      <h2>Настройки</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={save}>
          <Divider>Налоги</Divider>
          <Form.Item label="Ставка налога, %" name="tax_rate"><InputNumber style={{ width: 200 }} min={0} max={100} /></Form.Item>
          <Form.Item label="НДС, %" name="vat_rate"><InputNumber style={{ width: 200 }} min={0} max={100} /></Form.Item>

          <Divider>КТР / ИРП (еженедельно)</Divider>
          <Form.Item label="КТР" name="ktr_value">
            <Input style={{ width: 300 }} placeholder="Введите значение КТР" />
          </Form.Item>
          {settings.ktr_updated_at?.value && <Tag color="blue">Обновлено: {settings.ktr_updated_at.value.slice(0,16)}</Tag>}
          <Form.Item label="ИРП" name="irp_value">
            <Input style={{ width: 300 }} placeholder="Введите значение ИРП" />
          </Form.Item>
          {settings.irp_updated_at?.value && <Tag color="blue">Обновлено: {settings.irp_updated_at.value.slice(0,16)}</Tag>}

          <Divider>API</Divider>
          <Form.Item label="WB API Token" name="wb_api_token"><Input.TextArea rows={2} style={{ width: '100%' }} /></Form.Item>

          <Button type="primary" htmlType="submit" size="large">Сохранить</Button>
        </Form>
      </Card>
    </div>
  );
};
export default Settings;
