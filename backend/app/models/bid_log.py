from sqlalchemy import Column, Integer, String, Float, DateTime, func
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
