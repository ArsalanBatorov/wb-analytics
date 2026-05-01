from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, func, UniqueConstraint
from app.database import Base

class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, nullable=False)
    norm_query = Column(String(500), nullable=False)
    target_position = Column(Integer, default=1)
    max_bid = Column(Integer, default=1000)
    current_bid = Column(Integer, default=0)
    custom_bid = Column(Integer, nullable=True, default=None)
    is_bidding_active = Column(Boolean, default=False)
    frequency = Column(Integer, default=0)
    avg_position = Column(Float, default=0)
    current_position = Column(Integer, default=0)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpm = Column(Float, default=0)
    spend = Column(Float, default=0)
    add_to_cart = Column(Integer, default=0)
    cart_price = Column(Float, default=0)
    is_auto_minus = Column(Boolean, default=False)
    auto_minus_threshold = Column(Integer, default=100)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("campaign_id", "nm_id", "norm_query", name="uq_cluster"),
    )
