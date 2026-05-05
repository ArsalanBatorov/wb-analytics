/**
 * Страница «Настройки».
 *
 * Поля «ИЛ» и «ИРП» — это коэффициенты из кабинета WB, обновляются еженедельно.
 * В коде/БД они называются ktr/irp по историческим причинам, но в UI и в расчёте
 * логистики применяются именно как ИЛ (индекс локализации) и ИРП (индекс
 * распределения продаж) согласно официальной формуле WB:
 *   Логистика = (FL + EL × (vol−1)) × ИЛ + цена × ИРП/100
 *
 * Уведомление об устаревании: если ktr_updated_at старше 7 дней — красный тег.
 */
import { useEffect, useState } from "react";
import {
  Card, Form, Input, InputNumber, Button, Tag, Tooltip, Typography, Space, message, Divider,
} from "antd";
import { InfoCircleOutlined, EyeInvisibleOutlined, EyeTwoTone } from "@ant-design/icons";
import { fetchSettings, updateGlobalSettings } from "../api/client";

const { Title, Text } = Typography;

// Сколько прошло дней с даты updated_at (ISO-строка)
function daysSince(iso: string | undefined | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  const ms = Date.now() - d.getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

// Индикатор свежести: зелёный <7 дней, жёлтый 7-13, красный 14+
function FreshnessTag({ days, label }: { days: number | null; label: string }) {
  if (days === null) return <Tag color="default">{label}: не задан</Tag>;
  if (days < 7)  return <Tag color="green">{label}: обновлён {days} дн. назад</Tag>;
  if (days < 14) return <Tag color="orange">⚠️ {label}: обновлён {days} дн. назад — пора обновить</Tag>;
  return <Tag color="red">⚠️ {label}: не обновлялся {days} дн.! Скопируйте свежее значение из кабинета WB</Tag>;
}

export default function Settings() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [ktrUpdated, setKtrUpdated] = useState<string | null>(null);
  const [irpUpdated, setIrpUpdated] = useState<string | null>(null);

  const ktrDays = daysSince(ktrUpdated);
  const irpDays = daysSince(irpUpdated);

  useEffect(() => {
    setLoading(true);
    fetchSettings()
      .then((r: any) => {
        // Бэкенд отдаёт { settings: {...} } с плоскими строковыми значениями
        const s = r?.settings ?? r ?? {};
        form.setFieldsValue({
          tax_rate:     parseFloat(s.tax_rate ?? "0") || 0,
          vat_rate:     parseFloat(s.vat_rate ?? "0") || 0,
          ktr:          parseFloat(s.ktr      ?? "1.07") || 1.07,
          irp:          parseFloat(s.irp      ?? "0")    || 0,
          wb_api_token: s.wb_api_token ?? "",
        });
        setKtrUpdated(s.ktr_updated_at ?? null);
        setIrpUpdated(s.irp_updated_at ?? null);
      })
      .finally(() => setLoading(false));
  }, [form]);

  const onSave = async () => {
    try {
      const v = await form.validateFields();
      setSaving(true);
      await updateGlobalSettings(v);
      message.success("Настройки сохранены");
      // Перечитываем, чтобы обновить даты updated_at
      const r: any = await fetchSettings();
      const s = r?.settings ?? r ?? {};
      setKtrUpdated(s.ktr_updated_at ?? null);
      setIrpUpdated(s.irp_updated_at ?? null);
    } catch (e: any) {
      message.error("Ошибка сохранения: " + (e?.message ?? e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 800 }}>
      <Title level={3} style={{ marginTop: 0 }}>Настройки</Title>

      <Form form={form} layout="vertical" disabled={loading}>

        {/* ===== Налоги ===== */}
        <Card title="Налоги" style={{ marginBottom: 16 }}>
          <Space size="large" wrap>
            <Form.Item label="Ставка налога, %" name="tax_rate" style={{ marginBottom: 0 }}>
              <InputNumber min={0} max={100} step={0.1} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item label="НДС, %" name="vat_rate" style={{ marginBottom: 0 }}>
              <InputNumber min={0} max={100} step={0.1} style={{ width: 160 }} />
            </Form.Item>
          </Space>
        </Card>

        {/* ===== Индексы WB (еженедельно) ===== */}
        <Card
          title={
            <Space>
              <span>Индексы WB (обновляются еженедельно)</span>
              <Tooltip title={
                <>
                  <div><b>Формула логистики WB:</b></div>
                  <div>Логистика = (FL + EL × (vol−1)) × <b>ИЛ</b> + цена × <b>ИРП</b>/100</div>
                  <div style={{ marginTop: 8 }}>Значения берутся из вашего кабинета WB → раздел «Логистика и хранение» → «Индексы локализации и распределения продаж».</div>
                </>
              }>
                <InfoCircleOutlined style={{ color: "#1677ff" }} />
              </Tooltip>
            </Space>
          }
          style={{ marginBottom: 16 }}
        >
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div>
              <Form.Item
                label={
                  <Space>
                    <span>ИЛ — Индекс локализации</span>
                    <Tooltip title="Из кабинета WB. Обычно 0.5 – 2.0. Применяется как множитель к стоимости логистики: base × ИЛ. Если меньше 1 — скидка, больше 1 — наценка.">
                      <InfoCircleOutlined style={{ color: "#999" }} />
                    </Tooltip>
                  </Space>
                }
                name="ktr"
                style={{ marginBottom: 4 }}
              >
                <InputNumber min={0.1} max={5} step={0.01} precision={2} style={{ width: 200 }} />
              </Form.Item>
              <FreshnessTag days={ktrDays} label="ИЛ" />
            </div>

            <div>
              <Form.Item
                label={
                  <Space>
                    <span>ИРП — Индекс распределения продаж, %</span>
                    <Tooltip title="Из кабинета WB. Процент от цены товара, добавляемый к стоимости логистики: + цена × ИРП/100. Может быть 0% для некоторых категорий.">
                      <InfoCircleOutlined style={{ color: "#999" }} />
                    </Tooltip>
                  </Space>
                }
                name="irp"
                style={{ marginBottom: 4 }}
              >
                <InputNumber min={0} max={10} step={0.01} precision={2} style={{ width: 200 }} addonAfter="%" />
              </Form.Item>
              <FreshnessTag days={irpDays} label="ИРП" />
            </div>
          </Space>
        </Card>

        {/* ===== API ===== */}
        <Card title="API" style={{ marginBottom: 16 }}>
          <Form.Item
            label={
              <Space>
                <span>WB API Token</span>
                <Tooltip title="Токен из личного кабинета WB → Настройки → Доступ к API. Длинная строка вида eyJhbGc...">
                  <InfoCircleOutlined style={{ color: "#999" }} />
                </Tooltip>
              </Space>
            }
            name="wb_api_token"
          >
            <Input.Password
              iconRender={(visible) => visible ? <EyeTwoTone /> : <EyeInvisibleOutlined />}
              placeholder="eyJhbGc..."
            />
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Токен хранится в БД в открытом виде. После замены не забудьте перезапустить синхронизацию.
          </Text>
        </Card>

        <Button type="primary" size="large" onClick={onSave} loading={saving}>
          Сохранить
        </Button>
      </Form>
    </div>
  );
}
