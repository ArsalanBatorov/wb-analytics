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

// ============================================================
// === Margin endpoints (FACT cash-method, /api/margin/*) =====
// ============================================================
// Источник: realization_daily_stats (тот же, что финотчёт WB)
// margin = net_payout − COGS − ad_spend (комиссия и эквайринг
// уже учтены в ppvz_for_pay)

export interface MarginSummary {
  date_from: string;
  date_to: string;
  days: number;
  sales_count: number;
  returns_count: number;
  net_qty: number;
  sales_revenue: number;
  returns_revenue: number;
  to_pay: number;
  logistics: number;
  storage: number;
  deduction: number;
  penalty: number;
  acceptance: number;
  commission: number;
  acquiring: number;
  cogs: number;
  ad_spend: number;
  net_payout: number;
  margin: number;
  margin_pct: number;
}

export interface MarginDailyRow {
  date: string;
  sales_count: number;
  returns_count: number;
  sales_revenue: number;
  logistics: number;
  storage: number;
  deduction: number;
  cogs: number;
  ad_spend: number;
  net_payout: number;
  margin: number;
  margin_pct: number;
}

export interface MarginProductRow {
  nm_id: number;
  sales_count: number;
  returns_count: number;
  net_qty: number;
  sales_revenue: number;
  returns_revenue: number;
  logistics: number;
  storage: number;
  acceptance: number;
  deduction: number;
  penalty: number;
  commission: number;
  acquiring: number;
  cogs: number;
  ad_spend: number;
  net_payout: number;
  margin: number;
  margin_pct: number;
}

export const fetchMarginSummary = (p: Period) =>
  api.get<{ summary: MarginSummary }>(
    `/margin/summary?date_from=${p.date_from}&date_to=${p.date_to}`
  ).then(r => r.data.summary);

export const fetchMarginDaily = (p: Period) =>
  api.get<{ rows: MarginDailyRow[] }>(
    `/margin/daily?date_from=${p.date_from}&date_to=${p.date_to}`
  ).then(r => r.data.rows);

export const fetchMarginProducts = (p: Period) =>
  api.get<{ products: MarginProductRow[] }>(
    `/margin/products?date_from=${p.date_from}&date_to=${p.date_to}`
  ).then(r => r.data.products);

// ============== План/Факт (расчётный, источник product_daily_stats) ==============

export interface PlanFactMetric {
  key: string;
  title: string;
  plan_per_day: number | null;
  fact_per_day: number | null;
  forecast: number | null;
  plan_total: number | null;
  fact_total: number | null;
  pct: number | null;
}

export interface PlanFactSummary {
  date_from: string;
  date_to: string;
  plan_month: string;
  days_in_month: number;
  period_days: number;
  fact_days: number;
  plan: any;
  fact: any;
  metrics: PlanFactMetric[];
}

export interface PlanFactProduct {
  nm_id: number;
  vendor_code: string;
  title: string;
  orders_qty: number;
  orders_revenue: number;
  buyouts_qty: number;
  buyouts_revenue: number;
  margin: number;
  ad_spend: number;
  drr: number;
}

export interface MonthlyPlan {
  month: string;
  plan_orders_qty: number;
  plan_orders_revenue: number;
  plan_buyouts_qty: number;
  plan_buyouts_revenue: number;
  plan_margin: number;
  exists: boolean;
}

export const fetchPlanFactSummary = (p: Period, planMonth?: string) =>
  api.get<PlanFactSummary>(
    `/plan-fact/summary?date_from=${p.date_from}&date_to=${p.date_to}` +
    (planMonth ? `&plan_month=${planMonth}` : "")
  ).then(r => r.data);

export const fetchPlanFactProducts = (p: Period) =>
  api.get<{ products: PlanFactProduct[] }>(
    `/plan-fact/products?date_from=${p.date_from}&date_to=${p.date_to}`
  ).then(r => r.data.products);

export const fetchMonthlyPlan = (month: string) =>
  api.get<MonthlyPlan>(`/plans/?month=${month}`).then(r => r.data);

export const updateMonthlyPlan = (data: {
  month: string;
  plan_orders_qty: number;
  plan_orders_revenue: number;
  plan_buyouts_qty: number;
  plan_buyouts_revenue: number;
  plan_margin: number;
}) =>
  api.put<MonthlyPlan>(`/plans/`, data).then(r => r.data);

// ============================================================
// Locator API
// ============================================================

const LOCATOR_BASE = '/api/locator';

export async function fetchLocatorSummary() {
  const r = await fetch(LOCATOR_BASE + '/summary');
  if (!r.ok) throw new Error('Locator summary failed');
  return r.json();
}

export async function fetchLocatorStocks(article?: string, warehouse?: string) {
  const params = new URLSearchParams();
  if (article) params.set('article', article);
  if (warehouse) params.set('warehouse', warehouse);
  const r = await fetch(LOCATOR_BASE + '/stocks?' + params.toString());
  if (!r.ok) throw new Error('Locator stocks failed');
  return r.json();
}

export async function fetchLocatorDL() {
  const r = await fetch(LOCATOR_BASE + '/dl');
  if (!r.ok) throw new Error('Locator DL failed');
  return r.json();
}

export async function fetchLocatorIRPHistory() {
  const r = await fetch(LOCATOR_BASE + '/irp-history');
  if (!r.ok) throw new Error('Locator IRP history failed');
  return r.json();
}

export async function fetchLocatorQuickWins() {
  const r = await fetch(LOCATOR_BASE + '/quick-wins');
  if (!r.ok) throw new Error('Locator quick-wins failed');
  return r.json();
}

export async function fetchLocatorRecommendations() {
  const r = await fetch(LOCATOR_BASE + '/recommendations');
  if (!r.ok) throw new Error('Locator recommendations failed');
  return r.json();
}

export async function fetchLocatorPacking(generate = false) {
  const r = await fetch(LOCATOR_BASE + '/packing?generate=' + generate);
  if (!r.ok) throw new Error('Locator packing failed');
  return r.json();
}

export async function fetchLocatorAlerts() {
  const r = await fetch(LOCATOR_BASE + '/alerts');
  if (!r.ok) throw new Error('Locator alerts failed');
  return r.json();
}
