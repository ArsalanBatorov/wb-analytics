from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func, UniqueConstraint
from app.database import Base


class ClusterDailyStat(Base):
    __tablename__ = "cluster_daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, nullable=False)
    norm_query = Column(String(500), nullable=False)
    stat_date = Column(Date, nullable=False)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    spend = Column(Float, default=0)
    add_to_cart = Column(Integer, default=0)
    orders = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("cluster_id", "stat_date", name="uq_cluster_daily"),
    )
