from fastapi import APIRouter, Depends, HTTPException
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
