import asyncio
from datetime import datetime, timedelta, date
from app.celery_app import celery_app
from app.services.wb_api.token_loader import ensure_token


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.statistics.collect_stats")
def collect_stats():
    _run_async(_collect())


async def _collect():
    if not await ensure_token():
        return
    from app.database import AsyncSessionFactory
    from app.services.stats_collector import stats_collector
    async with AsyncSessionFactory() as db:
        await stats_collector.collect(db)


@celery_app.task(name="app.tasks.statistics.sync_campaigns")
def sync_campaigns():
    _run_async(_sync())


async def _sync():
    if not await ensure_token():
        print("[SYNC] No token")
        return

    from app.database import AsyncSessionFactory
    from app.services.wb_api.client import wb_client
    from app.models.campaign import Campaign
    from app.models.cluster import Cluster
    from app.models.cluster_daily_stats import ClusterDailyStat
    from sqlalchemy import select
    import httpx

    async with AsyncSessionFactory() as db:
        adverts = await wb_client.get_adverts()
        if not adverts:
            print("[SYNC] No adverts from WB")
            return
        print(f"[SYNC] Got {len(adverts)} adverts from WB")

        active_ids = []

        for adv in adverts:
            adv_id = adv.get("id")
            if not adv_id:
                continue

            name = adv.get("settings", {}).get("name", "")
            status = adv.get("status", 0)
            payment_type = adv.get("settings", {}).get("payment_type", "")
            bid_type = adv.get("bid_type", "")

            existing = (await db.execute(
                select(Campaign).where(Campaign.wb_campaign_id == adv_id)
            )).scalar_one_or_none()

            if existing:
                existing.name = name
                existing.status = status
                existing.payment_type = payment_type
                existing.bid_type = bid_type
            else:
                db.add(Campaign(
                    wb_campaign_id=adv_id, name=name, status=status,
                    payment_type=payment_type, bid_type=bid_type,
                ))

            nm_settings = adv.get("nm_settings") or []
            for nm in nm_settings:
                nm_id = nm.get("nm_id", 0)
                subject = nm.get("subject", {})
                subject_name = subject.get("name", "")
                bids = nm.get("bids_kopecks", {})
                search_bid = bids.get("search", 0)
                norm_query = subject_name if subject_name else f"nm_{nm_id}"

                existing_cluster = (await db.execute(
                    select(Cluster).where(
                        Cluster.campaign_id == adv_id,
                        Cluster.nm_id == nm_id,
                        Cluster.norm_query == norm_query,
                    )
                )).scalar_one_or_none()

                if existing_cluster:
                    existing_cluster.current_bid = search_bid // 100
                else:
                    db.add(Cluster(
                        campaign_id=adv_id, nm_id=nm_id, norm_query=norm_query,
                        current_bid=search_bid // 100, max_bid=search_bid // 100 + 200,
                        target_position=1, is_bidding_active=False,
                    ))

            if status == 9:
                active_ids.append(adv_id)

        await db.commit()

        # --- Load keyword stats per day ---
        now = datetime.utcnow()
        date_from = (now - timedelta(days=6)).strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")
        keywords_loaded = 0
        daily_saved = 0

        for cid in active_ids:
            try:
                resp = await wb_client._request(
                    "GET", "/adv/v0/stats/keywords",
                    limiter_key="campaigns",
                    params={"advert_id": cid, "from": date_from, "to": date_to}
                )
                if not resp or resp.status_code != 200:
                    continue

                data = resp.json()
                keywords_list = data.get("keywords") or []
                camp_cluster = (await db.execute(
                    select(Cluster).where(Cluster.campaign_id == cid)
                )).scalars().first()
                nm_id = camp_cluster.nm_id if camp_cluster else 0

                kw_totals = {}
                kw_daily = {}

                for day_entry in keywords_list:
                    day_date = day_entry.get("date", "")[:10]
                    for kw in day_entry.get("stats") or []:
                        keyword = kw.get("keyword", "")
                        if not keyword:
                            continue
                        v = kw.get("views", 0)
                        c = kw.get("clicks", 0)
                        s = kw.get("sum", 0.0)

                        if keyword not in kw_totals:
                            kw_totals[keyword] = {"views": 0, "clicks": 0, "spend": 0.0}
                        kw_totals[keyword]["views"] += v
                        kw_totals[keyword]["clicks"] += c
                        kw_totals[keyword]["spend"] += s

                        if day_date:
                            dk = (keyword, day_date)
                            if dk not in kw_daily:
                                kw_daily[dk] = {"views": 0, "clicks": 0, "spend": 0.0}
                            kw_daily[dk]["views"] += v
                            kw_daily[dk]["clicks"] += c
                            kw_daily[dk]["spend"] += s

                for keyword, stats in kw_totals.items():
                    views = stats["views"]
                    clicks = stats["clicks"]
                    spend = stats["spend"]
                    ctr = round(clicks / views * 100, 2) if views > 0 else 0
                    cpc = round(spend / clicks, 2) if clicks > 0 else 0

                    existing_kw = (await db.execute(
                        select(Cluster).where(
                            Cluster.campaign_id == cid,
                            Cluster.norm_query == keyword,
                        )
                    )).scalar_one_or_none()

                    if existing_kw:
                        existing_kw.views = views
                        existing_kw.clicks = clicks
                        existing_kw.spend = spend
                        existing_kw.ctr = ctr
                        existing_kw.cpc = cpc
                    else:
                        db.add(Cluster(
                            campaign_id=cid, nm_id=nm_id, norm_query=keyword,
                            current_bid=0, max_bid=1000,
                            target_position=1, is_bidding_active=False,
                            views=views, clicks=clicks, spend=spend,
                            ctr=ctr, cpc=cpc,
                        ))
                    keywords_loaded += 1

                await db.flush()

                for (keyword, day_date), dstats in kw_daily.items():
                    cluster = (await db.execute(
                        select(Cluster).where(
                            Cluster.campaign_id == cid,
                            Cluster.norm_query == keyword,
                        )
                    )).scalar_one_or_none()
                    if not cluster:
                        continue

                    views = dstats["views"]
                    clicks = dstats["clicks"]
                    spend = dstats["spend"]
                    if views == 0 and clicks == 0:
                        continue

                    ctr = round(clicks / views * 100, 2) if views > 0 else 0
                    cpc = round(spend / clicks, 2) if clicks > 0 else 0
                    sd = date.fromisoformat(day_date)

                    existing_daily = (await db.execute(
                        select(ClusterDailyStat).where(
                            ClusterDailyStat.cluster_id == cluster.id,
                            ClusterDailyStat.stat_date == sd,
                        )
                    )).scalar_one_or_none()

                    if existing_daily:
                        existing_daily.views = views
                        existing_daily.clicks = clicks
                        existing_daily.spend = round(spend, 2)
                        existing_daily.ctr = ctr
                        existing_daily.cpc = cpc
                    else:
                        db.add(ClusterDailyStat(
                            cluster_id=cluster.id,
                            campaign_id=cid,
                            nm_id=cluster.nm_id,
                            norm_query=keyword,
                            stat_date=sd,
                            views=views,
                            clicks=clicks,
                            spend=round(spend, 2),
                            ctr=ctr,
                            cpc=cpc,
                        ))
                    daily_saved += 1

                await db.commit()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[SYNC] Keywords error for {cid}: {e}")

        # --- Load fullstats for atbs/orders per nm_id ---
        atbs_total = 0
        orders_total = 0
        for cid in active_ids:
            try:
                await asyncio.sleep(2)
                resp = await wb_client._request(
                    "GET", "/adv/v3/fullstats",
                    limiter_key="campaigns",
                    params={"ids": str(cid), "beginDate": date_from, "endDate": date_to}
                )
                if not resp or resp.status_code != 200:
                    print(f"[SYNC] fullstats {cid}: {resp.status_code if resp else 'None'}")
                    continue

                fs_data = resp.json()
                if not isinstance(fs_data, list) or not fs_data:
                    continue

                adv_data = fs_data[0]
                # Collect atbs/orders per nm_id across all days and app types
                nm_atbs = {}  # {nm_id: total_atbs}
                nm_orders = {}

                for day_item in adv_data.get("days", []):
                    for app_item in day_item.get("apps", []):
                        for nm_item in app_item.get("nms", []):
                            nm_id_fs = nm_item.get("nmId", 0)
                            atbs = nm_item.get("atbs", 0)
                            orders = nm_item.get("orders", 0)
                            nm_atbs[nm_id_fs] = nm_atbs.get(nm_id_fs, 0) + atbs
                            nm_orders[nm_id_fs] = nm_orders.get(nm_id_fs, 0) + orders

                # Distribute atbs/orders to clusters proportionally by views
                for nm_id_fs, total_atbs in nm_atbs.items():
                    total_ord = nm_orders.get(nm_id_fs, 0)
                    if total_atbs == 0 and total_ord == 0:
                        continue

                    clusters_for_nm = (await db.execute(
                        select(Cluster).where(
                            Cluster.campaign_id == cid,
                            Cluster.nm_id == nm_id_fs,
                        )
                    )).scalars().all()

                    if not clusters_for_nm:
                        continue

                    total_views_nm = sum(c.views or 0 for c in clusters_for_nm)

                    for cl in clusters_for_nm:
                        if total_views_nm > 0:
                            ratio = (cl.views or 0) / total_views_nm
                        else:
                            ratio = 1.0 / len(clusters_for_nm)
                        cl.add_to_cart = max(0, round(total_atbs * ratio))

                    atbs_total += total_atbs
                    orders_total += total_ord

                await db.commit()
                print(f"[SYNC] fullstats {cid}: atbs={sum(nm_atbs.values())}, orders={sum(nm_orders.values())}")

            except Exception as e:
                print(f"[SYNC] fullstats error for {cid}: {e}")

        total = (await db.execute(select(Campaign))).scalars().all()
        total_clusters = (await db.execute(select(Cluster))).scalars().all()
        print(f"[SYNC] Done: {len(total)} campaigns, {len(total_clusters)} clusters, {keywords_loaded} kw, {daily_saved} daily, {atbs_total} atbs, {orders_total} orders")


@celery_app.task(name="app.tasks.statistics.daily_data_sync")
def daily_data_sync():
    """Full data sync: products, stats, ads, realization, stocks."""
    _run_async(_daily_sync())


async def _daily_sync():
    if not await ensure_token():
        print("[DAILY_SYNC] No token")
        return

    from app.services.data_sync import (
        sync_products_and_dimensions,
        sync_daily_stats,
        sync_ad_stats,
        sync_realization_daily,
        sync_stocks,
    )

    today = date.today()
    d30_ago = today - timedelta(days=30)

    print(f"[DAILY_SYNC] Starting full sync {d30_ago}..{today}")

    try:
        print("[DAILY_SYNC] 1/5 Products...")
        await sync_products_and_dimensions()
    except Exception as e:
        print(f"[DAILY_SYNC] Products error: {e}")

    try:
        print("[DAILY_SYNC] 2/5 Daily stats (30 days)...")
        await sync_daily_stats(days=30)
    except Exception as e:
        print(f"[DAILY_SYNC] Stats error: {e}")

    try:
        print("[DAILY_SYNC] 3/5 Ad stats (30 days)...")
        await sync_ad_stats(days=30)
    except Exception as e:
        print(f"[DAILY_SYNC] Ads error: {e}")

    try:
        print("[DAILY_SYNC] 4/5 Realization...")
        await sync_realization_daily(d30_ago, today)
    except Exception as e:
        print(f"[DAILY_SYNC] Realization error: {e}")

    try:
        print("[DAILY_SYNC] 5/5 Stocks...")
        await sync_stocks()
    except Exception as e:
        print(f"[DAILY_SYNC] Stocks error: {e}")

    print("[DAILY_SYNC] Complete!")
