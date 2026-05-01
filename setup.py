import os

BASE = "/root/wb-bidder"

files = {}

# ===== .env =====
files[".env"] = """WB_API_TOKEN=ВСТАВЬ_СВОЙ_ТОКЕН
DB_PASSWORD=WbBidder2026Secure
DATABASE_URL=postgresql+asyncpg://bidder:WbBidder2026Secure@localhost:5432/wb_bidder
DATABASE_URL_SYNC=postgresql+psycopg2://bidder:WbBidder2026Secure@localhost:5432/wb_bidder
REDIS_URL=redis://localhost:6379/1
APP_TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
"""

# ===== backend/app/__init__.py =====
files["backend/app/__init__.py"] = ""

# ===== backend/app/config.py =====
files["backend/app/config.py"] = '''import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    WB_API_TOKEN: str = os.getenv("WB_API_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://bidder:WbBidder2026Secure@localhost:5432/wb_bidder")
    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC", "postgresql+psycopg2://bidder:WbBidder2026Secure@localhost:5432/wb_bidder")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Europe/Moscow")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
'''

# ===== backend/app/database.py =====
files["backend/app/database.py"] = '''from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
'''

# ===== backend/app/models/__init__.py =====
files["backend/app/models/__init__.py"] = '''from app.models.campaign import Campaign
from app.models.cluster import Cluster
from app.models.schedule import Schedule
from app.models.bid_log import BidLog
from app.models.minus_queue import MinusQueue
'''

# ===== backend/app/models/campaign.py =====
files["backend/app/models/campaign.py"] = '''from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, func
from app.database import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wb_campaign_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(500), default="")
    status = Column(Integer, default=0)
    payment_type = Column(String(20), default="cpm")
    bid_type = Column(String(20), default="manual")
    is_bidder_active = Column(Boolean, default=False)
    max_bid = Column(Integer, default=1000)
    budget_total = Column(Float, default=0)
    balance = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
'''

# ===== backend/app/models/cluster.py =====
files["backend/app/models/cluster.py"] = '''from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, func, UniqueConstraint
from app.database import Base

class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, nullable=False)
    norm_query = Column(String(500), nullable=False)
    target_position = Column(Integer, default=1)
    max_bid = Column(Integer, default=1000)
    current_bid = Column(Integer, default=0)
    is_bidding_active = Column(Boolean, default=False)
    frequency = Column(Integer, default=0)
    avg_position = Column(Float, default=0)
    current_position = Column(Integer, default=0)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpm = Column(Float, default=0)
    spend = Column(Float, default=0)
    add_to_cart = Column(Integer, default=0)
    cart_price = Column(Float, default=0)
    is_auto_minus = Column(Boolean, default=False)
    auto_minus_threshold = Column(Integer, default=100)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("campaign_id", "nm_id", "norm_query", name="uq_cluster"),
    )
'''

# ===== backend/app/models/schedule.py =====
files["backend/app/models/schedule.py"] = '''from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    start_hour = Column(Integer, nullable=False, default=0)
    end_hour = Column(Integer, nullable=False, default=24)
    is_active = Column(Boolean, default=True)
    timezone = Column(String(50), default="Europe/Moscow")
    created_at = Column(DateTime, server_default=func.now())
'''

# ===== backend/app/models/bid_log.py =====
files["backend/app/models/bid_log.py"] = '''from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.database import Base

class BidLog(Base):
    __tablename__ = "bid_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, default=0)
    norm_query = Column(String(500), default="")
    old_bid = Column(Integer, default=0)
    new_bid = Column(Integer, default=0)
    position_before = Column(Integer, default=0)
    position_after = Column(Integer, default=0)
    reason = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())
'''

# ===== backend/app/models/minus_queue.py =====
files["backend/app/models/minus_queue.py"] = '''from sqlalchemy import Column, Integer, String, DateTime, func, UniqueConstraint
from app.database import Base

class MinusQueue(Base):
    __tablename__ = "minus_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, nullable=False)
    norm_query = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    views_at_creation = Column(Integer, default=0)
    views_current = Column(Integer, default=0)
    threshold = Column(Integer, default=100)
    retry_count = Column(Integer, default=0)
    error_message = Column(String(500), default="")
    reason = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("campaign_id", "nm_id", "norm_query", name="uq_minus"),
    )
'''

# ===== backend/app/services/__init__.py =====
files["backend/app/services/__init__.py"] = ""

# ===== backend/app/services/wb_api/__init__.py =====
files["backend/app/services/wb_api/__init__.py"] = ""

# ===== backend/app/services/wb_api/rate_limiter.py =====
files["backend/app/services/wb_api/rate_limiter.py"] = '''import asyncio
import time

class TokenBucketLimiter:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
                self.last_refill = time.monotonic()
            else:
                self.tokens -= 1
'''

# ===== backend/app/services/wb_api/client.py =====
files["backend/app/services/wb_api/client.py"] = '''import asyncio
import logging
import httpx
from app.config import settings
from app.services.wb_api.rate_limiter import TokenBucketLimiter

logger = logging.getLogger(__name__)

class WBApiClient:
    BASE_URL = "https://advert-api.wildberries.ru"

    LIMITERS = {
        "campaigns": TokenBucketLimiter(rate=5, burst=5),
        "bids": TokenBucketLimiter(rate=5, burst=5),
        "bids_recommendations": TokenBucketLimiter(rate=0.083, burst=1),
        "bids_min": TokenBucketLimiter(rate=0.33, burst=1),
        "normquery": TokenBucketLimiter(rate=5, burst=5),
        "normquery_stats": TokenBucketLimiter(rate=0.167, burst=1),
        "fullstats": TokenBucketLimiter(rate=0.05, burst=1),
        "balance": TokenBucketLimiter(rate=1, burst=1),
        "budget": TokenBucketLimiter(rate=4, burst=4),
        "start_pause": TokenBucketLimiter(rate=5, burst=5),
        "minus": TokenBucketLimiter(rate=5, burst=5),
    }

    def __init__(self):
        self.token = settings.WB_API_TOKEN
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": self.token},
            timeout=30.0,
        )

    async def _request(self, method, url, limiter_key="campaigns", **kwargs):
        limiter = self.LIMITERS.get(limiter_key, self.LIMITERS["campaigns"])
        max_retries = 4
        for attempt in range(max_retries):
            await limiter.acquire()
            try:
                resp = await self.client.request(method, url, **kwargs)
                remaining = resp.headers.get("X-Ratelimit-Remaining")
                if remaining and int(remaining) < 2:
                    await asyncio.sleep(1)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("X-Ratelimit-Retry", 5))
                    logger.warning(f"429 on {url}, retry after {retry_after}s")
                    await asyncio.sleep(retry_after * (attempt + 1))
                    continue
                if resp.status_code >= 500:
                    logger.warning(f"{resp.status_code} on {url}, retry {attempt+1}")
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                return resp
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                logger.warning(f"Connection error on {url}: {e}, retry {attempt+1}")
                await asyncio.sleep(2 * (attempt + 1))
        return None

    async def get_campaigns(self):
        resp = await self._request("GET", "/adv/v1/promotion/count", limiter_key="campaigns")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def get_campaign_details(self, campaign_ids: list):
        resp = await self._request("POST", "/adv/v1/promotion/adverts", limiter_key="campaigns", json=campaign_ids)
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def start_campaign(self, campaign_id: int):
        resp = await self._request("GET", f"/adv/v0/start", limiter_key="start_pause", params={"id": campaign_id})
        return resp and resp.status_code in (200, 204)

    async def pause_campaign(self, campaign_id: int):
        resp = await self._request("GET", f"/adv/v0/pause", limiter_key="start_pause", params={"id": campaign_id})
        return resp and resp.status_code in (200, 204)

    async def set_bids(self, campaign_id: int, bids: list):
        payload = {"advertId": campaign_id, "type": 8, "cpm": bids[0]["cpm"] if bids else 0, "param": bids[0]["param"] if bids else 0}
        resp = await self._request("PATCH", "/adv/v0/cpm", limiter_key="bids", json=payload)
        return resp and resp.status_code in (200, 204)

    async def get_normquery_list(self, campaign_id: int):
        resp = await self._request("GET", f"/adv/v0/normquery", limiter_key="normquery", params={"id": campaign_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def get_normquery_bids(self, campaign_id: int):
        resp = await self._request("POST", "/adv/v0/normquery/get-bids", limiter_key="normquery", json={"id": campaign_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def set_normquery_bids(self, campaign_id: int, bids: list):
        resp = await self._request("POST", "/adv/v0/normquery/bids", limiter_key="normquery", json={"id": campaign_id, "bids": bids})
        return resp and resp.status_code in (200, 204)

    async def get_normquery_stats(self, campaign_id: int):
        resp = await self._request("POST", "/adv/v0/normquery/stats", limiter_key="normquery_stats", json={"id": campaign_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def get_fullstats(self, campaign_ids: list):
        resp = await self._request("POST", "/adv/v2/fullstats", limiter_key="fullstats", json=campaign_ids)
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def get_balance(self):
        resp = await self._request("GET", "/adv/v1/balance", limiter_key="balance")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def get_budget(self, campaign_id: int):
        resp = await self._request("GET", "/adv/v1/budget", limiter_key="budget", params={"id": campaign_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def set_minus_phrases(self, campaign_id: int, nm_id: int, phrases: list):
        payload = {"id": campaign_id, "nmId": nm_id, "phrases": phrases}
        resp = await self._request("POST", "/adv/v0/normquery/set-minus", limiter_key="minus", json=payload)
        return resp and resp.status_code in (200, 204)

    async def get_bids_recommendations(self, campaign_id: int):
        resp = await self._request("GET", f"/adv/v0/bids/recommendations", limiter_key="bids_recommendations", params={"id": campaign_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    async def close(self):
        await self.client.aclose()

wb_client = WBApiClient()
'''

# ===== backend/app/services/bidder.py =====
files["backend/app/services/bidder.py"] = '''import logging
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
'''

# ===== backend/app/services/scheduler.py =====
files["backend/app/services/scheduler.py"] = '''import logging
from datetime import datetime
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.campaign import Campaign
from app.models.schedule import Schedule
from app.services.wb_api.client import wb_client

logger = logging.getLogger(__name__)

class ScheduleManager:
    async def check_schedules(self, db: AsyncSession):
        campaigns = (await db.execute(select(Campaign).where(Campaign.status.in_([9, 11])))).scalars().all()

        for campaign in campaigns:
            schedules = (await db.execute(
                select(Schedule).where(Schedule.campaign_id == campaign.wb_campaign_id, Schedule.is_active == True)
            )).scalars().all()

            if not schedules:
                continue

            tz = pytz.timezone(schedules[0].timezone if schedules else "Europe/Moscow")
            now = datetime.now(tz)
            current_day = now.weekday()
            current_hour = now.hour

            should_run = False
            for s in schedules:
                if s.day_of_week == current_day and s.start_hour <= current_hour < s.end_hour:
                    should_run = True
                    break

            if should_run and campaign.status == 11:
                success = await wb_client.start_campaign(campaign.wb_campaign_id)
                if success:
                    campaign.status = 9
                    logger.info(f"Started campaign {campaign.wb_campaign_id} by schedule")
            elif not should_run and campaign.status == 9:
                has_any_schedule = len(schedules) > 0
                if has_any_schedule:
                    success = await wb_client.pause_campaign(campaign.wb_campaign_id)
                    if success:
                        campaign.status = 11
                        logger.info(f"Paused campaign {campaign.wb_campaign_id} by schedule")

        await db.commit()

schedule_manager = ScheduleManager()
'''

# ===== backend/app/services/auto_minus.py =====
files["backend/app/services/auto_minus.py"] = '''import logging
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
'''

# ===== backend/app/services/stats_collector.py =====
files["backend/app/services/stats_collector.py"] = '''import logging
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
'''

# ===== backend/app/tasks/__init__.py =====
files["backend/app/tasks/__init__.py"] = ""

# ===== backend/app/celery_app.py =====
files["backend/app/celery_app.py"] = '''from celery import Celery
from app.config import settings

celery_app = Celery(
    "wb_bidder",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.APP_TIMEZONE,
    enable_utc=True,
    worker_max_tasks_per_child=1000,
    beat_schedule={
        "bidding-cycle": {"task": "app.tasks.bidding.run_bidding", "schedule": 35.0},
        "schedule-check": {"task": "app.tasks.scheduling.check_schedule", "schedule": 60.0},
        "stats-collection": {"task": "app.tasks.statistics.collect_stats", "schedule": 300.0},
        "campaign-sync": {"task": "app.tasks.statistics.sync_campaigns", "schedule": 600.0},
        "deferred-minus": {"task": "app.tasks.minus.process_minus_queue", "schedule": 300.0},
    },
)
'''

# ===== backend/app/tasks/bidding.py =====
files["backend/app/tasks/bidding.py"] = '''import asyncio
from app.celery_app import celery_app
from app.database import async_session
from app.services.bidder import bidder_engine

@celery_app.task(name="app.tasks.bidding.run_bidding")
def run_bidding():
    asyncio.run(_run())

async def _run():
    async with async_session() as db:
        await bidder_engine.run_cycle(db)
'''

# ===== backend/app/tasks/scheduling.py =====
files["backend/app/tasks/scheduling.py"] = '''import asyncio
from app.celery_app import celery_app
from app.database import async_session
from app.services.scheduler import schedule_manager

@celery_app.task(name="app.tasks.scheduling.check_schedule")
def check_schedule():
    asyncio.run(_run())

async def _run():
    async with async_session() as db:
        await schedule_manager.check_schedules(db)
'''

# ===== backend/app/tasks/statistics.py =====
files["backend/app/tasks/statistics.py"] = '''import asyncio
from app.celery_app import celery_app
from app.database import async_session
from app.services.stats_collector import stats_collector
from app.services.wb_api.client import wb_client
from app.models.campaign import Campaign
from sqlalchemy import select

@celery_app.task(name="app.tasks.statistics.collect_stats")
def collect_stats():
    asyncio.run(_collect())

async def _collect():
    async with async_session() as db:
        await stats_collector.collect(db)

@celery_app.task(name="app.tasks.statistics.sync_campaigns")
def sync_campaigns():
    asyncio.run(_sync())

async def _sync():
    data = await wb_client.get_campaigns()
    if not data:
        return
    adverts = data.get("adverts", []) if isinstance(data, dict) else []
    campaign_ids = []
    for group in adverts:
        for c in group.get("advert_list", []):
            campaign_ids.append(c.get("advertId", 0))

    if not campaign_ids:
        return

    details = await wb_client.get_campaign_details(campaign_ids)
    if not details:
        return

    async with async_session() as db:
        for d in details:
            wb_id = d.get("advertId", 0)
            existing = (await db.execute(
                select(Campaign).where(Campaign.wb_campaign_id == wb_id)
            )).scalar_one_or_none()

            if existing:
                existing.name = d.get("name", existing.name)
                existing.status = d.get("status", existing.status)
                existing.payment_type = d.get("paymentType", existing.payment_type)
            else:
                campaign = Campaign(
                    wb_campaign_id=wb_id,
                    name=d.get("name", ""),
                    status=d.get("status", 0),
                    payment_type=d.get("paymentType", "cpm"),
                )
                db.add(campaign)

        await db.commit()
'''

# ===== backend/app/tasks/minus.py =====
files["backend/app/tasks/minus.py"] = '''import asyncio
from app.celery_app import celery_app
from app.database import async_session
from app.services.auto_minus import minus_manager

@celery_app.task(name="app.tasks.minus.process_minus_queue")
def process_minus_queue():
    asyncio.run(_run())

async def _run():
    async with async_session() as db:
        await minus_manager.process_queue(db)
'''

# ===== backend/app/api/__init__.py =====
files["backend/app/api/__init__.py"] = ""

# ===== backend/app/api/dashboard.py =====
files["backend/app/api/dashboard.py"] = '''from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.campaign import Campaign
from app.models.cluster import Cluster

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    campaigns = (await db.execute(select(Campaign))).scalars().all()
    total_clusters = (await db.execute(select(func.count(Cluster.id)))).scalar() or 0
    active_campaigns = len([c for c in campaigns if c.status == 9])
    total_spend = (await db.execute(select(func.sum(Cluster.spend)))).scalar() or 0

    return {
        "total_campaigns": len(campaigns),
        "active_campaigns": active_campaigns,
        "total_clusters": total_clusters,
        "total_spend": round(total_spend, 2),
        "campaigns": [
            {
                "id": c.id,
                "wb_campaign_id": c.wb_campaign_id,
                "name": c.name,
                "status": c.status,
                "is_bidder_active": c.is_bidder_active,
                "budget_total": c.budget_total,
                "balance": c.balance,
            }
            for c in campaigns
        ],
    }
'''

# ===== backend/app/api/campaigns.py =====
files["backend/app/api/campaigns.py"] = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.campaign import Campaign

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

@router.post("/sync")
async def sync_now():
    from app.tasks.statistics import sync_campaigns
    sync_campaigns.delay()
    return {"ok": True, "message": "Sync started"}
'''

# ===== backend/app/api/clusters.py =====
files["backend/app/api/clusters.py"] = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.cluster import Cluster

router = APIRouter(prefix="/clusters", tags=["Clusters"])

class ClusterUpdate(BaseModel):
    target_position: int | None = None
    max_bid: int | None = None
    is_bidding_active: bool | None = None

@router.get("/{campaign_id}")
async def get_clusters(campaign_id: int, db: AsyncSession = Depends(get_db)):
    clusters = (await db.execute(
        select(Cluster).where(Cluster.campaign_id == campaign_id).order_by(Cluster.spend.desc())
    )).scalars().all()
    return [
        {
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
            "current_position": c.current_position,
            "views": c.views,
            "clicks": c.clicks,
            "ctr": c.ctr,
            "cpc": c.cpc,
            "cpm": c.cpm,
            "spend": c.spend,
            "add_to_cart": c.add_to_cart,
            "cart_price": c.cart_price,
            "is_auto_minus": c.is_auto_minus,
        }
        for c in clusters
    ]

@router.patch("/{cluster_id}")
async def update_cluster(cluster_id: int, data: ClusterUpdate, db: AsyncSession = Depends(get_db)):
    cluster = (await db.execute(select(Cluster).where(Cluster.id == cluster_id))).scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if data.target_position is not None:
        cluster.target_position = data.target_position
    if data.max_bid is not None:
        cluster.max_bid = data.max_bid
    if data.is_bidding_active is not None:
        cluster.is_bidding_active = data.is_bidding_active
    await db.commit()
    return {"ok": True}
'''

# ===== backend/app/api/schedule.py =====
files["backend/app/api/schedule.py"] = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.schedule import Schedule

router = APIRouter(prefix="/schedule", tags=["Schedule"])

class ScheduleCreate(BaseModel):
    campaign_id: int
    day_of_week: int
    start_hour: int = 0
    end_hour: int = 24
    is_active: bool = True
    timezone: str = "Europe/Moscow"

class ScheduleBulk(BaseModel):
    campaign_id: int
    schedules: list[ScheduleCreate]

@router.get("/{campaign_id}")
async def get_schedule(campaign_id: int, db: AsyncSession = Depends(get_db)):
    schedules = (await db.execute(
        select(Schedule).where(Schedule.campaign_id == campaign_id).order_by(Schedule.day_of_week)
    )).scalars().all()
    return [
        {
            "id": s.id,
            "campaign_id": s.campaign_id,
            "day_of_week": s.day_of_week,
            "start_hour": s.start_hour,
            "end_hour": s.end_hour,
            "is_active": s.is_active,
            "timezone": s.timezone,
        }
        for s in schedules
    ]

@router.post("")
async def create_schedule(data: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    schedule = Schedule(**data.model_dump())
    db.add(schedule)
    await db.commit()
    return {"ok": True, "id": schedule.id}

@router.put("/bulk")
async def bulk_update(data: ScheduleBulk, db: AsyncSession = Depends(get_db)):
    await db.execute(
        select(Schedule).where(Schedule.campaign_id == data.campaign_id)
    )
    existing = (await db.execute(
        select(Schedule).where(Schedule.campaign_id == data.campaign_id)
    )).scalars().all()
    for s in existing:
        await db.delete(s)

    for s in data.schedules:
        schedule = Schedule(**s.model_dump())
        db.add(schedule)
    await db.commit()
    return {"ok": True}

@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    schedule = (await db.execute(select(Schedule).where(Schedule.id == schedule_id))).scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.commit()
    return {"ok": True}
'''

# ===== backend/app/api/minus_queue.py =====
files["backend/app/api/minus_queue.py"] = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.minus_queue import MinusQueue

router = APIRouter(prefix="/minus", tags=["Minus Queue"])

class MinusAdd(BaseModel):
    campaign_id: int
    nm_id: int
    norm_query: str
    reason: str = ""

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
            "views_current": i.views_current,
            "threshold": i.threshold,
            "retry_count": i.retry_count,
            "error_message": i.error_message,
            "reason": i.reason,
            "created_at": str(i.created_at),
        }
        for i in items
    ]

@router.post("/queue")
async def add_to_queue(data: MinusAdd, db: AsyncSession = Depends(get_db)):
    item = MinusQueue(
        campaign_id=data.campaign_id,
        nm_id=data.nm_id,
        norm_query=data.norm_query,
        reason=data.reason,
        status="pending",
    )
    db.add(item)
    await db.commit()
    return {"ok": True, "id": item.id}

@router.delete("/queue/{item_id}")
async def cancel_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(MinusQueue).where(MinusQueue.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = "cancelled"
    await db.commit()
    return {"ok": True}
'''

# ===== backend/app/api/stats.py =====
files["backend/app/api/stats.py"] = '''from fastapi import APIRouter, Depends
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
'''

# ===== backend/app/main.py =====
files["backend/app/main.py"] = '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import dashboard, campaigns, clusters, schedule, minus_queue, stats

app = FastAPI(title="WB Bidder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(campaigns.router)
app.include_router(clusters.router)
app.include_router(schedule.router)
app.include_router(minus_queue.router)
app.include_router(stats.router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "wb-bidder"}
'''

# ===== alembic.ini =====
files["backend/alembic.ini"] = '''[alembic]
script_location = alembic
sqlalchemy.url = postgresql+psycopg2://bidder:WbBidder2026Secure@localhost:5432/wb_bidder

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
'''

# ===== alembic/env.py =====
files["backend/alembic/env.py"] = '''from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app.models import *

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

# ===== alembic/script.py.mako =====
files["backend/alembic/script.py.mako"] = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''

# Create all files
for path, content in files.items():
    full_path = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    print(f"Created: {path}")

# Create empty dirs
for d in ["backend/alembic/versions"]:
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
    print(f"Created dir: {d}")

print("\n=== All backend files created! ===")
