from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import date as date_type
from app.database import get_db
from app.models.cluster import Cluster
from app.models.cluster_daily_stats import ClusterDailyStat
from app.services.wb_api.client import wb_client

router = APIRouter(prefix="/clusters", tags=["Clusters"])


class ClusterUpdate(BaseModel):
    target_position: Optional[int] = None
    max_bid: Optional[int] = None
    is_bidding_active: Optional[bool] = None
    current_bid: Optional[int] = None


@router.get("/{campaign_id}")
async def get_clusters(
    campaign_id: int,
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    clusters = (
        await db.execute(
            select(Cluster)
            .where(Cluster.campaign_id == campaign_id)
            .order_by(Cluster.spend.desc())
        )
    ).scalars().all()

    daily_map = {}
    if date_from and date_to:
        d_from = date_type.fromisoformat(date_from)
        d_to = date_type.fromisoformat(date_to)
        rows = (
            await db.execute(
                select(
                    ClusterDailyStat.cluster_id,
                    func.sum(ClusterDailyStat.views).label("views"),
                    func.sum(ClusterDailyStat.clicks).label("clicks"),
                    func.sum(ClusterDailyStat.spend).label("spend"),
                    func.sum(ClusterDailyStat.add_to_cart).label("add_to_cart"),
                    func.sum(ClusterDailyStat.orders).label("orders"),
                )
                .where(
                    ClusterDailyStat.campaign_id == campaign_id,
                    ClusterDailyStat.stat_date >= d_from,
                    ClusterDailyStat.stat_date <= d_to,
                )
                .group_by(ClusterDailyStat.cluster_id)
            )
        ).all()
        for r in rows:
            daily_map[r.cluster_id] = {
                "views": int(r.views or 0),
                "clicks": int(r.clicks or 0),
                "spend": float(r.spend or 0),
                "add_to_cart": int(r.add_to_cart or 0),
                "orders": int(r.orders or 0),
            }

    result = []
    for c in clusters:
        views = int(c.views or 0)
        clicks = int(c.clicks or 0)
        spend = float(c.spend or 0)
        atc = int(c.add_to_cart or 0)
        orders = int(getattr(c, 'orders', 0) or 0)

        if c.id in daily_map:
            d = daily_map[c.id]
            views = d["views"]
            clicks = d["clicks"]
            spend = d["spend"]
            atc = d["add_to_cart"]
            orders = d["orders"]

        ctr = round(clicks / views * 100, 2) if views > 0 else 0
        cpc = round(spend / clicks, 2) if clicks > 0 else 0
        cpm = round(spend / views * 1000, 0) if views > 0 else 0

        result.append({
            "id": c.id,
            "campaign_id": c.campaign_id,
            "nm_id": c.nm_id,
            "norm_query": c.norm_query,
            "target_position": c.target_position,
            "max_bid": c.max_bid,
            "current_bid": c.current_bid,
            "is_bidding_active": c.is_bidding_active,
            "frequency": c.frequency,
            "avg_position": c.avg_position,
            "views": views,
            "clicks": clicks,
            "ctr": ctr,
            "cpc": cpc,
            "cpm": cpm,
            "spend": spend,
            "add_to_cart": atc,
            "orders": orders,
            "is_auto_minus": c.is_auto_minus,
        })
    return result


@router.patch("/{cluster_id}")
async def update_cluster(cluster_id: int, data: ClusterUpdate, db: AsyncSession = Depends(get_db)):
    cluster = (await db.execute(select(Cluster).where(Cluster.id == cluster_id))).scalar_one_or_none()
    if not cluster:
        return {"error": "not found"}
    if data.target_position is not None:
        cluster.target_position = data.target_position
    if data.max_bid is not None:
        cluster.max_bid = data.max_bid
    if data.is_bidding_active is not None:
        cluster.is_bidding_active = data.is_bidding_active
    if data.current_bid is not None:
        cluster.current_bid = data.current_bid
    await db.commit()
    return {"ok": True}


@router.post("/sync-bids/{campaign_id}")
async def sync_bids_from_wb(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Load real per-cluster bids from WB API and save to DB"""
    from app.services.wb_api.client import wb_client

    clusters = (
        await db.execute(
            select(Cluster).where(Cluster.campaign_id == campaign_id)
        )
    ).scalars().all()

    if not clusters:
        return {"error": "no clusters"}

    nm_ids = list(set(c.nm_id for c in clusters))
    nq_map = {c.norm_query: c for c in clusters}
    updated = 0

    for nm_id in nm_ids:
        bids = await wb_client.get_normquery_bids(campaign_id, nm_id)
        for b in bids:
            nq = b.get("norm_query", "")
            bid_rub = b.get("bid", 0)
            if nq in nq_map:
                cluster = nq_map[nq]
                cluster.current_bid = bid_rub
                updated += 1

    await db.commit()
    return {"ok": True, "updated": updated, "total": len(clusters)}


class SetCpmRequest(BaseModel):
    campaign_id: int
    nm_id: int
    bids: list  # [{"norm_query": "...", "cpm": 500}, ...]


class SetUniformCpmRequest(BaseModel):
    campaign_id: int
    nm_id: int
    cpm: float  # rub
    norm_queries: list  # list of norm_query strings


@router.post("/set-cpm")
async def set_cpm(data: SetCpmRequest, db: AsyncSession = Depends(get_db)):
    """Set CPM for specific clusters via WB API"""
    from app.services.wb_api.client import wb_client
    bids = []
    for b in data.bids:
        bids.append({
            "norm_query": b["norm_query"],
            "bid_kopecks": int(b["cpm"] * 100),
        })
    success = await wb_client.set_normquery_bids(data.campaign_id, data.nm_id, bids)
    if success:
        # Update DB
        for b in data.bids:
            cluster = (await db.execute(
                select(Cluster).where(
                    Cluster.campaign_id == data.campaign_id,
                    Cluster.norm_query == b["norm_query"],
                )
            )).scalar_one_or_none()
            if cluster:
                cluster.cpm = b["cpm"]
        await db.commit()
    return {"ok": success, "updated": len(bids)}


@router.post("/set-uniform-cpm")
async def set_uniform_cpm(data: SetUniformCpmRequest, db: AsyncSession = Depends(get_db)):
    """Set the same CPM for multiple clusters via WB API"""
    from app.services.wb_api.client import wb_client
    bid_kopecks = int(data.cpm * 100)
    bids = [{"norm_query": nq, "bid_kopecks": bid_kopecks} for nq in data.norm_queries]
    success = await wb_client.set_normquery_bids(data.campaign_id, data.nm_id, bids)
    if success:
        for nq in data.norm_queries:
            cluster = (await db.execute(
                select(Cluster).where(
                    Cluster.campaign_id == data.campaign_id,
                    Cluster.norm_query == nq,
                )
            )).scalar_one_or_none()
            if cluster:
                cluster.cpm = data.cpm
        await db.commit()
    return {"ok": success, "updated": len(data.norm_queries)}

@router.get("/fullstats/{campaign_id}")
async def get_fullstats(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get campaign fullstats (atbs, orders) from WB API"""
    from datetime import date, timedelta
    begin = (date.today() - timedelta(days=6)).isoformat()
    end = date.today().isoformat()
    
    resp = await wb_client.get_fullstats(campaign_id, begin, end)
    return resp

@router.get("/keyword-stats/{campaign_id}")
async def get_keyword_stats(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get per-keyword stats with atbs and orders (normquery v1)"""
    resp = await wb_client.get_keyword_stats(campaign_id)
    return resp
