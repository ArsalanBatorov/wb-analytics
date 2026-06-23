/**
 * Типы для API /api/locator/dl-real
 * React + TypeScript + Ant Design
 */

/** Региональная детализация по размеру */
export interface RegionDetail {
  /** Название региона */
  region: string;
  /** Общее количество заказов в регионе */
  orders_total: number;
  /** Количество локальных заказов в регионе */
  orders_local: number;
  /** Доля локальных заказов в регионе (%) */
  dl: number | null;
}

/** Детализация по складу */
export interface WarehouseDetail {
  /** Название региона */
  region: string;
  /** Название склада */
  warehouse: string;
  /** Количество заказов */
  orders: number;
  /** Количество выкупов */
  buyout: number;
  /** Остаток на складе */
  stock: number;
}

/** Информация о размере товара */
export interface SizeInfo {
  /** Размер */
  size: string;
  /** Доля локальных заказов по этому размеру (%) */
  dl: number | null;
  /** Коэффициент транспортной работы (КТР) */
  ktr: number | null;
  /** Коэффициент развития продаж (КРП) */
  krp: number | null;
  /** Общее количество заказов по размеру */
  ordersTotal: number;
  /** Количество локальных заказов по размеру */
  ordersLocal: number;
  /** Остаток на складе WB по размеру */
  stockWB: number | null;
  /** Процент выкупа по размеру (%) */
  buyoutPercent: number | null;
  /** Дней до окончания остатка (Days to OOS) */
  daysToOOS: number | null;
  /** Детализация по регионам */
  byRegion: RegionDetail[];
  /** Детализация по складам */
  byWarehouse: WarehouseDetail[];
  /** Данные о поставках в пути */
  inTransit?: InTransitData;
  /** Взвешенный вклад размера в ИРП артикула (%) */
  ilWeight: number;
}

/** Информация об артикуле */
export interface ArticleInfo {
  /** ID артикула в системе WB */
  nmId: string;
  /** Артикул продавца */
  vendorCode: string;
  /** Категория товара */
  subject: string | null;
  /** Дата импорта данных */
  importedAt: string;
  /** Доля локальных заказов по артикулу (%) */
  dl: number | null;
  /** Коэффициент транспортной работы (КТР) артикула */
  ktr: number | null;
  /** Коэффициент развития продаж (КРП) артикула */
  krp: number | null;
  /** Общее количество заказов по артикулу */
  ordersTotal: number;
  /** Количество локальных заказов по артикулу */
  ordersLocal: number;
  /** Суммарный остаток на складах WB по артикулу */
  stockWB: number;
  /** Дней до окончания остатка по артикулу (Days to OOS) */
  daysToOOS: number | null;
  /** Взвешенный вклад артикула в ИРП (%) */
  ilWeight: number;
  /** Список размеров артикула */
  sizes: SizeInfo[];
}

/** Ответ API /api/locator/dl-real */
export interface LocatorDlRealResponse {
  /** Список артикулов */
  articles: ArticleInfo[];
  /** Интегральный индекс локальности (ИЛ) */
  il: number | null;
  /** Интегральный индекс развития продаж (ИРП) */
  irp: number | null;
  /** Общее количество заказов за период */
  totalOrders: number;
  /** Количество дней в отчётном периоде */
  periodDays: number;
  /** Дата начала периода (YYYY-MM-DD) */
  dateFrom: string | null;
  /** Дата окончания периода (YYYY-MM-DD) */
  dateTo: string | null;
  /** Дата последнего импорта geo-отчёта */
  importedAt: string | null;
}

// === ДОБАВЛЕНО ДЛЯ ЭТАПА 2 (ТОВАРЫ В ПУТИ) ===
export interface InTransitBatch {
  warehouse: string;
  quantity: number;
  eta: string;
}

export interface InTransitData {
  totalQty: number;
  batches: InTransitBatch[];
}

// Обновляем SizeInfo (добавляем поле inTransit)
// Если интерфейс уже существует, нужно его дополнить
