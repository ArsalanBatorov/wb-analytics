import asyncio
from app.celery_app import celery_app
from app.services.wb_api.token_loader import ensure_token

def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@celery_app.task(name="app.tasks.scheduling.check_schedule")
def check_schedule():
    _run_async(_schedule())

async def _schedule():
    if not await ensure_token():
        return
    from app.database import AsyncSessionFactory
    from app.services.scheduler import schedule_manager
    async with AsyncSessionFactory() as db:
        await schedule_manager.check_schedules(db)
