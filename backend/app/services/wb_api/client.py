"""
Wildberries API client — read-only operations.
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional, List

import httpx

logger = logging.getLogger(__name__)


class WBClient:
    def __init__(self):
        self.token = ""
        self.analytics_client: Optional[httpx.AsyncClient] = None
        self.adv_client: Optional[httpx.AsyncClient] = None
        self.common_client: Optional[httpx.AsyncClient] = None
        self.stats_client: Optional[httpx.AsyncClient] = None
        self.content_client: Optional[httpx.AsyncClient] = None

    def _headers(self):
        return {"Authorization": self.token}

    async def _ensure_clients(self):
        h = self._headers()
        if not self.analytics_client or self.analytics_client.is_closed:
            self.analytics_client = httpx.AsyncClient(
                base_url="https://seller-analytics-api.wildberries.ru",
                headers=h, timeout=30
            )
        if not self.adv_client or self.adv_client.is_closed:
            self.adv_client = httpx.AsyncClient(
                base_url="https://advert-api.wildberries.ru",
                headers=h, timeout=30
            )
        if not self.common_client or self.common_client.is_closed:
            self.common_client = httpx.AsyncClient(
                base_url="https://common-api.wildberries.ru",
                headers=h, timeout=30
            )
        if not self.stats_client or self.stats_client.is_closed:
            self.stats_client = httpx.AsyncClient(
                base_url="https://statistics-api.wildberries.ru",
                headers=h, timeout=30
            )
        if not self.content_client or self.content_client.is_closed:
            self.content_client = httpx.AsyncClient(
                base_url="https://content-api.wildberries.ru",
                headers=h, timeout=30
            )

    def set_token(self, token: str):
        self.token = token
        # Reset clients so they pick up new token
        for attr in ['analytics_client', 'adv_client', 'common_client', 'stats_client', 'content_client']:
            c = getattr(self, attr, None)
            if c and not c.is_closed:
                asyncio.create_task(c.aclose())
            setattr(self, attr, None)

    # === Content API ===

    async def get_all_cards(self) -> list:
        """Fetch all product cards with dimensions."""
        await self._ensure_clients()
        all_cards = []
        cursor = {"limit": 100}

        for _ in range(20):  # max 2000 cards
            body = {
                "settings": {
                    "cursor": cursor,
                    "filter": {"withPhoto": -1}
                }
            }
            r = await self.content_client.post("/content/v2/get/cards/list", json=body)
            if r.status_code != 200:
                logger.error(f"Cards API error {r.status_code}: {r.text[:200]}")
                break
            data = r.json()
            cards = data.get("cards", [])
            if not cards:
                break
            all_cards.extend(cards)
            cur = data.get("cursor", {})
            cursor = {
                "limit": 100,
                "updatedAt": cur.get("updatedAt"),
                "nmID": cur.get("nmID")
            }
            if len(cards) < 100:
                break
            await asyncio.sleep(0.5)

        return all_cards

    # === Analytics API ===

    async def get_sales_funnel(self, nm_ids: list = None, start: str = None, end: str = None, page: int = 1):
        """Get sales funnel data."""
        await self._ensure_clients()
        if not start:
            start = (date.today() - timedelta(days=7)).isoformat()
        if not end:
            end = date.today().isoformat()

        body = {
            "selectedPeriod": {"start": start, "end": end},
            "page": page
        }
        if nm_ids:
            body["nmIDs"] = nm_ids

        r = await self.analytics_client.post("/api/analytics/v3/sales-funnel/products", json=body)
        if r.status_code == 200:
            return r.json()
        logger.error(f"Sales funnel error {r.status_code}: {r.text[:300]}")
        return None

    async def get_sales_history(self, nm_ids: list, start: str, end: str):
        """Get daily history for products."""
        await self._ensure_clients()
        body = {
            "nmIds": nm_ids,
            "selectedPeriod": {"start": start, "end": end}
        }
        r = await self.analytics_client.post("/api/analytics/v3/sales-funnel/products/history", json=body)
        if r.status_code == 200:
            return r.json()
        logger.error(f"History error {r.status_code}: {r.text[:300]}")
        return None

    # === Promotion API ===

    async def get_promotion_campaigns(self):
        """Get campaign list grouped by type/status."""
        await self._ensure_clients()
        r = await self.adv_client.get("/adv/v1/promotion/count")
        if r.status_code == 200:
            return r.json()
        logger.error(f"Promotion count error {r.status_code}: {r.text[:300]}")
        return None

    async def get_fullstats(self, campaign_id: int, date_from: str, date_to: str):
        """Get full advertising stats for a campaign."""
        await self._ensure_clients()
        r = await self.adv_client.get(
            f"/adv/v3/fullstats?ids={campaign_id}&beginDate={date_from}&endDate={date_to}"
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            logger.warning("Rate limited on fullstats, waiting 65s...")
            await asyncio.sleep(65)
            r = await self.adv_client.get(
                f"/adv/v3/fullstats?ids={campaign_id}&beginDate={date_from}&endDate={date_to}"
            )
            if r.status_code == 200:
                return r.json()
        logger.error(f"Fullstats error {r.status_code}: {r.text[:300]}")
        return None

    # === Common API (tariffs) ===

    async def get_commissions(self):
        """Get commission rates."""
        await self._ensure_clients()
        r = await self.common_client.get("/api/v1/tariffs/commission?locale=ru")
        if r.status_code == 200:
            return r.json().get("report", [])
        logger.error(f"Commission error {r.status_code}: {r.text[:300]}")
        return None

    async def get_box_tariffs(self):
        """Get box delivery tariffs."""
        await self._ensure_clients()
        today = date.today().isoformat()
        r = await self.common_client.get(f"/api/v1/tariffs/box?date={today}")
        if r.status_code == 200:
            return r.json()
        logger.error(f"Box tariffs error {r.status_code}: {r.text[:300]}")
        return None

    # === Statistics API ===

    async def get_stocks(self):
        """Get current stock levels."""
        await self._ensure_clients()
        date_from = (date.today() - timedelta(days=7)).isoformat()
        r = await self.stats_client.get(f"/api/v1/supplier/stocks?dateFrom={date_from}")
        if r.status_code == 200:
            return r.json()
        logger.error(f"Stocks error {r.status_code}: {r.text[:300]}")
        return None

    async def get_realization_report(self, date_from: str, date_to: str):
        """Get realization report."""
        await self._ensure_clients()
        r = await self.stats_client.get(
            f"/api/v5/supplier/reportDetailByPeriod?dateFrom={date_from}&dateTo={date_to}"
        )
        if r.status_code == 200:
            return r.json()
        logger.error(f"Realization error {r.status_code}: {r.text[:300]}")
        return None


wb_client = WBClient()
