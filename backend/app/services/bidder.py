import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cluster import Cluster
from app.models.campaign import Campaign
from app.models.bid_log import BidLog
from app.services.wb_api.client import wb_client

logger = logging.getLogger(__name__)

BID_STEP_UP = 50
BID_STEP_DOWN = 25
MIN_BID = 50

class BidderEngine:
    async def run_cycle(self, db: AsyncSession):
        campaigns = (await db.execute(
            select(Campaign).where(Campaign.is_bidder_active == True, Campaign.status == 9)
        )).scalars().all()

        for campaign in campaigns:
            clusters = (await db.execute(
                select(Cluster).where(
                    Cluster.campaign_id == campaign.wb_campaign_id,
                    Cluster.is_bidding_active == True,
                )
            )).scalars().all()

            if not clusters:
                continue

            normquery_bids = await wb_client.get_normquery_bids(campaign.wb_campaign_id)
            if not normquery_bids:
                continue

            bids_map = {}
            if isinstance(normquery_bids, list):
                for item in normquery_bids:
                    key = item.get("normQuery", "") or item.get("norm_query", "")
                    bids_map[key] = item

            bids_to_set = []
            for cluster in clusters:
                current_data = bids_map.get(cluster.norm_query, {})
                current_position = current_data.get("position", 0) or current_data.get("avg_position", 0)
                current_bid = current_data.get("bid", 0) or current_data.get("cpm", 0) or cluster.current_bid

                old_bid = current_bid
                target = cluster.target_position
                max_bid = min(cluster.max_bid, campaign.max_bid)

                if current_position == 0:
                    new_bid = current_bid
                elif current_position > target:
                    new_bid = min(current_bid + BID_STEP_UP, max_bid)
                elif current_position < target:
                    new_bid = max(current_bid - BID_STEP_DOWN, MIN_BID)
                else:
                    new_bid = current_bid

                if new_bid != old_bid:
                    bids_to_set.append({
                        "norm_query": cluster.norm_query,
                        "bid": new_bid,
                    })
                    log = BidLog(
                        campaign_id=campaign.wb_campaign_id,
                        nm_id=cluster.nm_id,
                        norm_query=cluster.norm_query,
                        old_bid=old_bid,
                        new_bid=new_bid,
                        position_before=int(current_position),
                        reason=f"pos {current_position} -> target {target}",
                    )
                    db.add(log)

                cluster.current_bid = new_bid
                cluster.current_position = int(current_position)

            if bids_to_set:
                formatted = [{"normQuery": b["norm_query"], "bid": b["bid"]} for b in bids_to_set]
                await wb_client.set_normquery_bids(campaign.wb_campaign_id, formatted)
                logger.info(f"Campaign {campaign.wb_campaign_id}: updated {len(bids_to_set)} bids")

        await db.commit()

bidder_engine = BidderEngine()
