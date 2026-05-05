/**
 * Корневой компонент. Пока показываем только страницу Margin.
 * Остальные страницы (Dashboard, Settings, Products, Campaigns) импортируют
 * несуществующие функции из client.ts и валят билд — включим обратно
 * по одной, добавляя недостающие функции.
 */
import { ConfigProvider, Layout } from "antd";
import ruRU from "antd/locale/ru_RU";
import Margin from "./pages/Margin";

const { Content } = Layout;

export default function App() {
  return (
    <ConfigProvider locale={ruRU}>
      <Layout style={{ minHeight: "100vh" }}>
        <Content style={{ background: "#f0f2f5" }}>
          <Margin />
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
