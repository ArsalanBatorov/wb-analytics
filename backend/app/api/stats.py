from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.bid_log import BidLog

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.get("/bid-logs/{campaign_id}")
async def get_bid_logs(campaign_id: int, limit: int = 100, db: AsyncSession = Depends(get_db)):
    logs = (await db.execute(
        select(BidLog)
        .where(BidLog.campaign_id == campaign_id)
        .order_by(BidLog.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": l.id,
            "campaign_id": l.campaign_id,
            "nm_id": l.nm_id,
            "norm_query": l.norm_query,
            "old_bid": l.old_bid,
            "new_bid": l.new_bid,
            "position_before": l.position_before,
            "reason": l.reason,
            "created_at": str(l.created_at),
        }
        for l in logs
    ]
