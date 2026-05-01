from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.campaign import Campaign
from app.services.wb_api.client import wb_client
from app.services.wb_api.token_loader import ensure_token

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


class CampaignUpdate(BaseModel):
    is_bidder_active: bool | None = None
    max_bid: int | None = None


@router.get("")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    campaigns = (await db.execute(select(Campaign))).scalars().all()
    return [
        {
            "id": c.id,
            "wb_campaign_id": c.wb_campaign_id,
            "name": c.name,
            "status": c.status,
            "payment_type": c.payment_type,
            "bid_type": c.bid_type,
            "is_bidder_active": c.is_bidder_active,
            "max_bid": c.max_bid,
            "budget_total": c.budget_total,
            "balance": c.balance,
        }
        for c in campaigns
    ]


@router.patch("/{campaign_id}")
async def update_campaign(campaign_id: int, data: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.wb_campaign_id == campaign_id)
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if data.is_bidder_active is not None:
        campaign.is_bidder_active = data.is_bidder_active
    if data.max_bid is not None:
        campaign.max_bid = data.max_bid
    await db.commit()
    return {"ok": True}


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.wb_campaign_id == campaign_id)
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await ensure_token()
    result = await wb_client.start_campaign(campaign_id)
    if result:
        campaign.status = 9
        await db.commit()
        return {"ok": True, "message": f"Campaign {campaign_id} started", "new_status": 9}
    else:
        raise HTTPException(status_code=400, detail="Failed to start campaign on WB. Check budget and campaign status.")


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.wb_campaign_id == campaign_id)
    )).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await ensure_token()
    result = await wb_client.pause_campaign(campaign_id)
    if result:
        campaign.status = 11
        await db.commit()
        return {"ok": True, "message": f"Campaign {campaign_id} paused", "new_status": 11}
    else:
        raise HTTPException(status_code=400, detail="Failed to pause campaign on WB.")


@router.post("/sync")
async def sync_now():
    from app.tasks.statistics import sync_campaigns
    sync_campaigns.delay()
    return {"ok": True, "message": "Sync started"}
