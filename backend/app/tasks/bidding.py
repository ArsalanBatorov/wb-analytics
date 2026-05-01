import asyncio
from app.celery_app import celery_app
from app.services.wb_api.token_loader import ensure_token


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.bidding.run_bidding")
def run_bidding():
    _run_async(_bidding())


async def _bidding():
    if not await ensure_token():
        return
    from app.database import AsyncSessionFactory
    from app.services.bidder import bidder_engine
    async with AsyncSessionFactory() as db:
        await bidder_engine.run_cycle(db)
