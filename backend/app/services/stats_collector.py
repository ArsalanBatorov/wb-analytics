import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.campaign import Campaign
from app.models.cluster import Cluster
from app.services.wb_api.client import wb_client

logger = logging.getLogger(__name__)

class StatsCollector:
    async def collect(self, db: AsyncSession):
        campaigns = (await db.execute(select(Campaign))).scalars().all()

        for campaign in campaigns:
            stats = await wb_client.get_normquery_stats(campaign.wb_campaign_id)
            if not stats or not isinstance(stats, list):
                continue

            for s in stats:
                nq = s.get("normQuery", "") or s.get("norm_query", "")
                if not nq:
                    continue

                existing = (await db.execute(
                    select(Cluster).where(
                        Cluster.campaign_id == campaign.wb_campaign_id,
                        Cluster.norm_query == nq,
                    )
                )).scalar_one_or_none()

                views = s.get("views", 0)
                clicks = s.get("clicks", 0)
                spend = s.get("spend", 0) or s.get("sum", 0)
                ctr = (clicks / views * 100) if views > 0 else 0
                cpc = (spend / clicks) if clicks > 0 else 0
                cpm = (spend / views * 1000) if views > 0 else 0
                add_to_cart = s.get("addToCart", 0) or s.get("atbs", 0)
                cart_price = (spend / add_to_cart) if add_to_cart > 0 else 0

                if existing:
                    existing.frequency = s.get("frequency", 0) or s.get("count", 0)
                    existing.avg_position = s.get("avgPosition", 0) or s.get("avg_position", 0)
                    existing.views = views
                    existing.clicks = clicks
                    existing.ctr = round(ctr, 2)
                    existing.cpc = round(cpc, 2)
                    existing.cpm = round(cpm, 2)
                    existing.spend = round(spend, 2)
                    existing.add_to_cart = add_to_cart
                    existing.cart_price = round(cart_price, 2)
                else:
                    nm_id = s.get("nmId", 0) or s.get("nm_id", 0)
                    cluster = Cluster(
                        campaign_id=campaign.wb_campaign_id,
                        nm_id=nm_id,
                        norm_query=nq,
                        frequency=s.get("frequency", 0) or s.get("count", 0),
                        avg_position=s.get("avgPosition", 0) or s.get("avg_position", 0),
                        views=views,
                        clicks=clicks,
                        ctr=round(ctr, 2),
                        cpc=round(cpc, 2),
                        cpm=round(cpm, 2),
                        spend=round(spend, 2),
                        add_to_cart=add_to_cart,
                        cart_price=round(cart_price, 2),
                    )
                    db.add(cluster)

        await db.commit()
        logger.info("Stats collection complete")

stats_collector = StatsCollector()
