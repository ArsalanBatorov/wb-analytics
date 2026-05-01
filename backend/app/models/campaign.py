from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, func
from app.database import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wb_campaign_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(500), default="")
    status = Column(Integer, default=0)
    payment_type = Column(String(20), default="cpm")
    bid_type = Column(String(20), default="manual")
    is_bidder_active = Column(Boolean, default=False)
    max_bid = Column(Integer, default=1000)
    budget_total = Column(Float, default=0)
    balance = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
