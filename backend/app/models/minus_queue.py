from sqlalchemy import Column, Integer, String, DateTime, func, UniqueConstraint
from app.database import Base

class MinusQueue(Base):
    __tablename__ = "minus_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(Integer, nullable=False)
    norm_query = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    views_at_creation = Column(Integer, default=0)
    views_current = Column(Integer, default=0)
    threshold = Column(Integer, default=100)
    retry_count = Column(Integer, default=0)
    error_message = Column(String(500), default="")
    reason = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("campaign_id", "nm_id", "norm_query", name="uq_minus"),
    )
