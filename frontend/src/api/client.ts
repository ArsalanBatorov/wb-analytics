import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// === Period helper ===
const fmtDate = (d: Date) => d.toISOString().slice(0, 10);
const daysAgo = (n: number) => {
  const d = new Date(); d.setDate(d.getDate() - n); return d;
};

export type Period = { date_from: string; date_to: string };

export const makePeriod = (days: number): Period => ({
  date_from: fmtDate(daysAgo(days)),
  date_to: fmtDate(new Date()),
});

export const makeCustomPeriod = (from: string, to: string): Period => ({
  date_from: from,
  date_to: to,
});

// === OLD model endpoints (keep for model mode) ===
export const fetchSummary = (days = 7) =>
  api.get(`/analytics/summary?days=${days}`).then((r) => r.data);

export const fetchProducts = (days = 7) =>
  api.get(`/analytics/products?days=${days}`).then((r) => r.data);

export const fetchProductDaily = (nmId: number, days = 7) =>
  api.get(`/analytics/products/${nmId}/daily?days=${days}`).then((r) => r.data);

export const fetchPlanStatus = () =>
  api.get("/analytics/plan-status").then((r) => r.data);

// === NEW financial endpoints (fact from WB realization report) ===
export const fetchFinancialSummary = (p: Period) =>
  api.get(`/analytics/financial-summary?date_from=${p.date_from}&date_to=${p.date_to}`).then((r) => r.data);

export const fetchFinancialDaily = (p: Period) =>
  api.get(`/analytics/financial-daily?date_from=${p.date_from}&date_to=${p.date_to}`).then((r) => r.data);

export const fetchFinancialProducts = (p: Period) =>
  api.get(`/analytics/financial-products?date_from=${p.date_from}&date_to=${p.date_to}`).then((r) => r.data);

export const fetchFinancialProductDaily = (nmId: number, p: Period) =>
  api.get(`/analytics/financial-products/${nmId}/daily?date_from=${p.date_from}&date_to=${p.date_to}`).then((r) => r.data);

// === Settings & sync ===
export const fetchSettings = () =>
  api.get("/settings/").then((r) => r.data);

export const updateGlobalSettings = (data: any) =>
  api.put("/settings/global", data).then((r) => r.data);

export const updateCostPrice = (nmId: number, costPrice: number) =>
  api.put("/settings/cost-price", { nm_id: nmId, cost_price: costPrice }).then((r) => r.data);

export const updatePlan = (nmId: number, month: string, planOrders: number) =>
  api.put("/settings/plan", { nm_id: nmId, month, plan_orders: planOrders }).then((r) => r.data);

export const syncAll = (days = 7) =>
  api.post(`/sync/full?days=${days}`).then((r) => r.data);

export const syncProducts = () =>
  api.post("/sync/products").then((r) => r.data);

export const syncAds = (days = 7) =>
  api.post(`/sync/ads?days=${days}`).then((r) => r.data);

// Advertising endpoints
export const fetchAdvertisingSummary = (p: Period) =>
  api.get(`/analytics/advertising-summary?date_from=${p.date_from}&date_to=${p.date_to}`).then(r => r.data);

export const fetchAdvertisingProducts = (p: Period) =>
  api.get(`/analytics/advertising-products?date_from=${p.date_from}&date_to=${p.date_to}`).then(r => r.data);

export const fetchAdvertisingDaily = (p: Period) =>
  api.get(`/analytics/advertising-daily?date_from=${p.date_from}&date_to=${p.date_to}`).then(r => r.data);

// Product daily stats (orders, buyouts, ad spend)
export const fetchProductDailyStats = (nmId: number, p: Period) =>
  api.get(`/analytics/product-daily-stats/${nmId}?date_from=${p.date_from}&date_to=${p.date_to}`).then(r => r.data);

export const fetchProductDrawer = (nmId: number, p: Period) =>
  api.get(`/analytics/product-drawer/${nmId}?date_from=${p.date_from}&date_to=${p.date_to}`).then(r => r.data);
