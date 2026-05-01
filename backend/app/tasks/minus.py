import asyncio
from app.celery_app import celery_app
from app.services.wb_api.token_loader import ensure_token

def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@celery_app.task(name="app.tasks.minus.process_minus_queue")
def process_minus_queue():
    _run_async(_minus())

async def _minus():
    if not await ensure_token():
        return
    from app.database import AsyncSessionFactory
    from app.services.auto_minus import minus_manager
    async with AsyncSessionFactory() as db:
        await minus_manager.process_queue(db)
