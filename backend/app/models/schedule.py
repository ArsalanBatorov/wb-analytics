from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
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
