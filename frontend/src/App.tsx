import React, { useState } from 'react';
import { ConfigProvider, theme, App as AntdApp, Layout, Menu } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import {
  DashboardOutlined,
  BarChartOutlined,
  RiseOutlined,
  DollarOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import LocatorDashboard from './pages/LocatorDashboard';
import PlanFact from './pages/PlanFact';
import Advertising from './pages/Advertising';
import Margin from './pages/Margin';
import Settings from './pages/Settings';
import 'dayjs/locale/ru';

const { Sider, Content } = Layout;

const menuItems = [
  { key: 'margin', icon: <DollarOutlined />, label: 'Фин. отчёт' },
  { key: 'locator', icon: <DashboardOutlined />, label: 'Локатор' },
  { key: 'plan-fact', icon: <BarChartOutlined />, label: 'План/Факт' },
  { key: 'advertising', icon: <RiseOutlined />, label: 'Реклама' },
  { key: 'settings', icon: <SettingOutlined />, label: 'Настройки' },
];

const components: Record<string, React.FC> = {
  margin: Margin,
  locator: LocatorDashboard,
  'plan-fact': PlanFact,
  advertising: Advertising,
  settings: Settings,
};

const App: React.FC = () => {
  const [activeKey, setActiveKey] = useState('margin');
  const Component = components[activeKey];

  return (
    <ConfigProvider
      locale={ruRU}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 6,
        },
      }}
    >
      <AntdApp>
        <Layout style={{ minHeight: '100vh' }}>
          <Sider breakpoint="lg" collapsedWidth="80">
            <div style={{ height: 32, margin: 16, color: '#fff', fontWeight: 'bold', fontSize: 18, textAlign: 'center' }}>
              WB
            </div>
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[activeKey]}
              items={menuItems}
              onClick={({ key }) => setActiveKey(key)}
            />
          </Sider>
          <Layout>
            <Content style={{ margin: 24 }}>
              <Component />
            </Content>
          </Layout>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
