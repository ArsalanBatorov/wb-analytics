from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.minus_queue import MinusQueue

router = APIRouter(prefix="/minus", tags=["Minus Queue"])


class MinusAdd(BaseModel):
    campaign_id: int
    nm_id: int
    norm_query: str
    reason: str = "manual"


class MinusBulk(BaseModel):
    campaign_id: int
    nm_id: int
    phrases: List[str]
    reason: str = "manual"


@router.get("/queue/{campaign_id}")
async def get_queue(campaign_id: int, status: str = None, db: AsyncSession = Depends(get_db)):
    query = select(MinusQueue).where(MinusQueue.campaign_id == campaign_id)
    if status:
        query = query.where(MinusQueue.status == status)
    items = (await db.execute(query.order_by(MinusQueue.created_at.desc()))).scalars().all()
    return [
        {
            "id": i.id,
            "campaign_id": i.campaign_id,
            "nm_id": i.nm_id,
            "norm_query": i.norm_query,
            "status": i.status,
            "retry_count": i.retry_count,
            "error_message": i.error_message,
            "reason": i.reason,
            "created_at": str(i.created_at),
        }
        for i in items
    ]


@router.post("/queue")
async def add_to_queue(data: MinusAdd, db: AsyncSession = Depends(get_db)):
    """Add single phrase to minus queue"""
    existing = (await db.execute(
        select(MinusQueue).where(
            MinusQueue.campaign_id == data.campaign_id,
            MinusQueue.nm_id == data.nm_id,
            MinusQueue.norm_query == data.norm_query,
            MinusQueue.status.notin_(["cancelled", "failed"]),
        )
    )).scalar_one_or_none()
    if existing:
        return {"ok": False, "error": "already in queue", "id": existing.id}

    item = MinusQueue(
        campaign_id=data.campaign_id,
        nm_id=data.nm_id,
        norm_query=data.norm_query,
        reason=data.reason,
        status="ready",
    )
    db.add(item)
    await db.commit()
    return {"ok": True, "id": item.id}


@router.post("/instant")
async def instant_minus(data: MinusBulk, db: AsyncSession = Depends(get_db)):
    """Send minus phrases to WB immediately (bulk)"""
    from app.services.wb_api.client import wb_client
    if not data.phrases:
        raise HTTPException(status_code=400, detail="No phrases provided")
    try:
        current = await wb_client.get_minus_phrases(data.campaign_id, data.nm_id)
        new_phrases = [p for p in data.phrases if p not in current]
        if not new_phrases:
            return {"ok": True, "added": 0, "message": "all already minused"}

        full_list = current + new_phrases
        success = await wb_client.set_minus_phrases(data.campaign_id, data.nm_id, full_list)

        # Log each phrase in queue
        for phrase in new_phrases:
            item = MinusQueue(
                campaign_id=data.campaign_id,
                nm_id=data.nm_id,
                norm_query=phrase,
                reason=data.reason,
                status="sent" if success else "failed",
            )
            db.add(item)
        await db.commit()

        return {"ok": success, "added": len(new_phrases), "total": len(full_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remove")
async def remove_minus(data: MinusBulk, db: AsyncSession = Depends(get_db)):
    """Remove phrases from WB minus list"""
    from app.services.wb_api.client import wb_client
    if not data.phrases:
        raise HTTPException(status_code=400, detail="No phrases provided")
    try:
        current = await wb_client.get_minus_phrases(data.campaign_id, data.nm_id)
        remove_set = set(data.phrases)
        new_list = [p for p in current if p not in remove_set]
        removed_count = len(current) - len(new_list)

        if removed_count == 0:
            return {"ok": True, "removed": 0, "message": "phrases not found in minus list"}

        success = await wb_client.set_minus_phrases(data.campaign_id, data.nm_id, new_list)
        return {"ok": success, "removed": removed_count, "remaining": len(new_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/queue/{item_id}")
async def cancel_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(MinusQueue).where(MinusQueue.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = "cancelled"
    await db.commit()
    return {"ok": True}


@router.get("/wb/{campaign_id}/{nm_id}")
async def get_wb_minus(campaign_id: int, nm_id: int):
    """Get current minus phrases directly from WB"""
    from app.services.wb_api.client import wb_client
    phrases = await wb_client.get_minus_phrases(campaign_id, nm_id)
    return {"phrases": phrases, "count": len(phrases)}
