import { useEffect, useState } from "react";
import { ConfigProvider, Layout, Menu, Alert, Button } from "antd";
import {
  FundProjectionScreenOutlined,
  NotificationOutlined,
  AccountBookOutlined,
  SettingOutlined,
  AimOutlined,
} from "@ant-design/icons";
import ruRU from "antd/locale/ru_RU";
import dayjs from "dayjs";
import "dayjs/locale/ru";
import updateLocale from "dayjs/plugin/updateLocale";

dayjs.extend(updateLocale);
dayjs.updateLocale("ru", {
  months: ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
  monthsShort: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
});
dayjs.locale("ru");

import PlanFact from "./pages/PlanFact";
import Margin from "./pages/Margin";
import Advertising from "./pages/Advertising";
import Settings from "./pages/Settings";
import LocatorDashboard from "./pages/LocatorDashboard";
import { fetchSettings } from "./api/client";

const { Sider, Content } = Layout;
type PageKey = "plan_fact" | "advertising" | "fin_report" | "settings" | "locator";

function daysSince(iso: string | undefined | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function StaleSettingsBanner({ onGoSettings }: { onGoSettings: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    fetchSettings()
      .then((r: any) => {
        const s = r?.settings ?? r ?? {};
        const ktrDays = daysSince(s.ktr_updated_at);
        const irpDays = daysSince(s.irp_updated_at);
        const stale: string[] = [];
        if (ktrDays === null) stale.push("ИЛ не задан");
        else if (ktrDays >= 7) stale.push(`ИЛ не обновлялся ${ktrDays} дн.`);
        if (irpDays === null) stale.push("ИРП не задан");
        else if (irpDays >= 7) stale.push(`ИРП не обновлялся ${irpDays} дн.`);
        if (stale.length > 0) {
          setMsg(stale.join(", ") + " — обновите значения из кабинета WB, иначе расчёт логистики будет неточным.");
        } else {
          setMsg(null);
        }
      })
      .catch(() => setMsg(null));
  }, []);
  if (!msg) return null;
  return (
    <Alert
      type="warning"
      showIcon
      message="Внимание: индексы WB устарели"
      description={msg}
      action={<Button size="small" onClick={onGoSettings}>Перейти в Настройки</Button>}
      style={{ margin: 16, marginBottom: 0 }}
      closable
    />
  );
}

const PAGES: Record<PageKey, { label: string; node: React.ReactNode }> = {
  plan_fact:   { label: "План/Факт",  node: <PlanFact /> },
  advertising: { label: "Реклама",    node: <Advertising /> },
  fin_report:  { label: "Фин. отчёт", node: <Margin /> },
  settings:    { label: "Настройки",  node: <Settings /> },
  locator:     { label: "Locator",    node: <LocatorDashboard /> },
};

export default function App() {
  const [page, setPage] = useState<PageKey>("locator");
  const [collapsed, setCollapsed] = useState(false);
  return (
    <ConfigProvider locale={ruRU}>
      <Layout style={{ minHeight: "100vh" }}>
        <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="light" width={200}>
          <div style={{ height: 48, margin: 8, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 600, color: "#1677ff" }}>
            {collapsed ? "WB" : "WB-Analytics"}
          </div>
          <Menu
            mode="inline"
            selectedKeys={[page]}
            onClick={(e) => setPage(e.key as PageKey)}
            items={[
              { key: "plan_fact",   icon: <FundProjectionScreenOutlined />, label: "План/Факт" },
              { key: "advertising", icon: <NotificationOutlined />,         label: "Реклама" },
              { key: "fin_report",  icon: <AccountBookOutlined />,          label: "Фин. отчёт" },
              { key: "settings",    icon: <SettingOutlined />,              label: "Настройки" },
              { key: "locator",     icon: <AimOutlined />,                  label: "Locator" },
            ]}
          />
        </Sider>
        <Content style={{ background: "#f0f2f5" }}>
          <StaleSettingsBanner onGoSettings={() => setPage("settings")} />
          {PAGES[page].node}
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
