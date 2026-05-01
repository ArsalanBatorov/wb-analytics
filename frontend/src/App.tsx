/**
 * Корневой компонент. Боковое меню переключает страницы.
 * Используем useState вместо react-router (минимум зависимостей).
 */
import { useState } from "react";
import { Layout, Menu, ConfigProvider } from "antd";
import {
  DashboardOutlined, DollarOutlined, ShoppingOutlined,
  RocketOutlined, SettingOutlined,
} from "@ant-design/icons";
import ruRU from "antd/locale/ru_RU";

import Dashboard from "./pages/Dashboard";
import Margin from "./pages/Margin";
import Products from "./pages/Products";
import Campaigns from "./pages/Campaigns";
import Settings from "./pages/Settings";

const { Sider, Content } = Layout;

type PageKey = "dashboard" | "margin" | "products" | "campaigns" | "settings";

const PAGES: Record<PageKey, { label: string; icon: any; component: React.FC }> = {
  dashboard: { label: "Дашборд",   icon: <DashboardOutlined />, component: Dashboard },
  margin:    { label: "Маржа",      icon: <DollarOutlined />,    component: Margin },
  products:  { label: "Товары",     icon: <ShoppingOutlined />,  component: Products },
  campaigns: { label: "Кампании",   icon: <RocketOutlined />,    component: Campaigns },
  settings:  { label: "Настройки",  icon: <SettingOutlined />,   component: Settings },
};

export default function App() {
  // Стартовая страница — Маржа (новая основная)
  const [page, setPage] = useState<PageKey>("margin");
  const [collapsed, setCollapsed] = useState(false);

  const PageComponent = PAGES[page].component;

  return (
    <ConfigProvider locale={ruRU}>
      <Layout style={{ minHeight: "100vh" }}>
        <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
          <div style={{
            color: "#fff", padding: 16, fontWeight: 700,
            fontSize: collapsed ? 14 : 18, textAlign: "center",
          }}>
            {collapsed ? "WB" : "WB Analytics"}
          </div>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[page]}
            onClick={({ key }) => setPage(key as PageKey)}
            items={Object.entries(PAGES).map(([k, v]) => ({
              key: k, icon: v.icon, label: v.label,
            }))}
          />
        </Sider>
        <Layout>
          <Content style={{ background: "#f0f2f5" }}>
            <PageComponent />
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
