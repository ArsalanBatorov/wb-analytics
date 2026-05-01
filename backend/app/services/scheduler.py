import logging
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
