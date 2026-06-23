import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.database import async_session
from app.models.settings import AppSettings
from app.services.wb_api.client import wb_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load token on startup
    try:
        async with async_session() as db:
            r = await db.execute(select(AppSettings).where(AppSettings.key == "wb_api_token"))
            s = r.scalar_one_or_none()
            if s and s.value:
                wb_client.set_token(s.value)
                logger.info(f"Token loaded ({len(s.value)} chars)")
            else:
                logger.warning("No API token in DB")
    except Exception as e:
        logger.error(f"Failed to load token: {e}")
    yield


app = FastAPI(title="WB Analytics", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.api.analytics import router as analytics_router
from app.api.settings import router as settings_router
from app.api.sync import router as sync_router
from app.api.margin import router as margin_router
from app.api.plan_fact import plan_fact_router, plans_router
from app.api.locator import router as locator_router
from app.api.truestat import router as truestat_router
from app.api.upload_stats import router as upload_router
from app.api.campaigns import router as campaigns_router

app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(sync_router)
app.include_router(margin_router)
app.include_router(plan_fact_router)
app.include_router(plans_router)
app.include_router(locator_router)
app.include_router(truestat_router)
app.include_router(upload_router)
app.include_router(campaigns_router)


@app.get("/health")
async def health():
    return {"status": "ok", "token_set": bool(wb_client.token)}
