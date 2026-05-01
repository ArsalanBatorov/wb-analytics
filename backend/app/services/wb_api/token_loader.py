from sqlalchemy import select
from app.models.settings import AppSettings
from app.services.wb_api.client import wb_client


async def ensure_token():
    """Load token from DB if current one is empty."""
    if wb_client.token and wb_client.token.startswith("ey"):
        return True
    try:
        from app.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            setting = (await db.execute(
                select(AppSettings).where(AppSettings.key == "wb_api_token")
            )).scalar_one_or_none()
            if setting and setting.value:
                wb_client.set_token(setting.value)
                print(f"[TOKEN] Loaded from DB, length={len(setting.value)}")
                return True
    except Exception as e:
        print(f"[TOKEN] Error loading: {e}")
    print("[TOKEN] No valid token found")
    return False
