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
            logger.warning(f"Skipping normquery stats for campaign {campaign.wb_campaign_id}: get_normquery_stats not implemented")

        await db.commit()
        logger.info("Stats collection complete")

stats_collector = StatsCollector()
