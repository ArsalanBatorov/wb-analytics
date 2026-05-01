from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base

class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(2000), default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
