from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.campaign import Campaign
from app.models.cluster import Cluster
from app.models.cluster_daily_stats import ClusterDailyStat

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
async def get_dashboard(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    campaigns = (await db.execute(select(Campaign))).scalars().all()
    total_clusters = (await db.execute(select(func.count(Cluster.id)))).scalar() or 0

    # If dates provided, aggregate from daily stats
    if date_from and date_to:
        q = select(
            func.sum(ClusterDailyStat.views).label("views"),
            func.sum(ClusterDailyStat.clicks).label("clicks"),
            func.sum(ClusterDailyStat.spend).label("spend"),
            func.sum(ClusterDailyStat.add_to_cart).label("add_to_cart"),
            func.sum(ClusterDailyStat.orders).label("orders"),
        ).where(
            ClusterDailyStat.stat_date >= date_from,
            ClusterDailyStat.stat_date <= date_to,
        )
        row = (await db.execute(q)).one_or_none()
        total_views = row.views or 0 if row else 0
        total_clicks = row.clicks or 0 if row else 0
        total_spend = round(row.spend or 0, 2) if row else 0
        total_atc = row.add_to_cart or 0 if row else 0
        total_orders = row.orders or 0 if row else 0
        total_ctr = round(total_clicks / total_views * 100, 2) if total_views > 0 else 0
        total_cpc = round(total_spend / total_clicks, 2) if total_clicks > 0 else 0

        # Per-campaign stats for the period
        camp_q = select(
            ClusterDailyStat.campaign_id,
            func.sum(ClusterDailyStat.views).label("views"),
            func.sum(ClusterDailyStat.clicks).label("clicks"),
            func.sum(ClusterDailyStat.spend).label("spend"),
            func.sum(ClusterDailyStat.orders).label("orders"),
        ).where(
            ClusterDailyStat.stat_date >= date_from,
            ClusterDailyStat.stat_date <= date_to,
        ).group_by(ClusterDailyStat.campaign_id)
        camp_stats = {r.campaign_id: r for r in (await db.execute(camp_q)).all()}
    else:
        # Default: use totals from clusters table
        agg = (await db.execute(select(
            func.sum(Cluster.views),
            func.sum(Cluster.clicks),
            func.sum(Cluster.spend),
        ))).one_or_none()
        total_views = agg[0] or 0 if agg else 0
        total_clicks = agg[1] or 0 if agg else 0
        total_spend = round(agg[2] or 0, 2) if agg else 0
        total_atc = 0
        total_orders = 0
        total_ctr = round(total_clicks / total_views * 100, 2) if total_views > 0 else 0
        total_cpc = round(total_spend / total_clicks, 2) if total_clicks > 0 else 0
        camp_stats = {}

    active_campaigns = len([c for c in campaigns if c.status == 9])

    camp_list = []
    for c in campaigns:
        cs = camp_stats.get(c.wb_campaign_id)
        camp_list.append({
            "id": c.id,
            "wb_campaign_id": c.wb_campaign_id,
            "name": c.name,
            "status": c.status,
            "is_bidder_active": c.is_bidder_active,
            "budget_total": c.budget_total,
            "balance": c.balance,
            "views": cs.views if cs else 0,
            "clicks": cs.clicks if cs else 0,
            "spend": round(cs.spend, 2) if cs else 0,
            "orders": cs.orders if cs else 0,
        })

    return {
        "total_campaigns": len(campaigns),
        "active_campaigns": active_campaigns,
        "total_clusters": total_clusters,
        "total_spend": total_spend,
        "total_views": total_views,
        "total_clicks": total_clicks,
        "total_ctr": total_ctr,
        "total_cpc": total_cpc,
        "total_orders": total_orders,
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "campaigns": camp_list,
    }
