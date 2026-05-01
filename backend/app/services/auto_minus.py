import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.minus_queue import MinusQueue
from app.models.bid_log import BidLog
from app.services.wb_api.client import wb_client

logger = logging.getLogger(__name__)

class DeferredMinusManager:
    async def process_queue(self, db: AsyncSession):
        pending = (await db.execute(
            select(MinusQueue).where(MinusQueue.status.in_(["pending", "ready"]))
        )).scalars().all()

        for item in pending:
            if item.status == "pending":
                stats = await wb_client.get_normquery_stats(item.campaign_id)
                if stats and isinstance(stats, list):
                    for s in stats:
                        nq = s.get("normQuery", "") or s.get("norm_query", "")
                        if nq == item.norm_query:
                            item.views_current = s.get("views", 0)
                            break

                if item.views_current >= item.threshold:
                    item.status = "ready"
                    logger.info(f"Minus queue item ready: {item.norm_query} ({item.views_current} views)")

            if item.status == "ready":
                try:
                    success = await wb_client.set_minus_phrases(
                        item.campaign_id, item.nm_id, [item.norm_query]
                    )
                    if success:
                        item.status = "sent"
                        log = BidLog(
                            campaign_id=item.campaign_id,
                            nm_id=item.nm_id,
                            norm_query=item.norm_query,
                            reason=f"auto-minus sent ({item.reason})",
                        )
                        db.add(log)
                        logger.info(f"Minus phrase sent: {item.norm_query}")
                    else:
                        item.retry_count += 1
                        if item.retry_count >= 5:
                            item.status = "failed"
                            item.error_message = "Max retries reached"
                except Exception as e:
                    item.retry_count += 1
                    item.error_message = str(e)[:500]
                    if item.retry_count >= 5:
                        item.status = "failed"

        await db.commit()

minus_manager = DeferredMinusManager()
