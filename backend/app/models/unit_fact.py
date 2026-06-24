from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, func
from app.database import Base


class UnitFact(Base):
    __tablename__ = "unit_fact"

    id = Column(Integer, primary_key=True, autoincrement=True)

    manager = Column(String, default="")
    vendor_code = Column(String, default="")
    size = Column(String, default="")
    row_type = Column(String, default="detail")

    sales_count = Column(Integer, default=0)
    returns_count = Column(Integer, default=0)
    returns_pct = Column(Float, default=0.0)
    net_sales = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    revenue_per_unit = Column(Float, default=0.0)
    cost_price_total = Column(Float, default=0.0)
    cost_price_per_unit = Column(Float, default=0.0)
    cost_price_pct = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    commission_pct = Column(Float, default=0.0)
    logistics_total = Column(Float, default=0.0)
    logistics_per_unit = Column(Float, default=0.0)
    logistics_pct = Column(Float, default=0.0)
    logistics_direct = Column(Float, default=0.0)
    logistics_direct_pct = Column(Float, default=0.0)
    logistics_return = Column(Float, default=0.0)
    logistics_return_pct = Column(Float, default=0.0)
    acquiring_penalty = Column(Float, default=0.0)
    ad_spend = Column(Float, default=0.0)
    ad_spend_per_unit = Column(Float, default=0.0)
    margin_per_unit = Column(Float, default=0.0)
    margin_pct = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    orders_4w = Column(Integer, default=0)
    sales_4w = Column(Integer, default=0)
    buyout_4w_pct = Column(Float, default=0.0)
    orders_18w = Column(Integer, default=0)
    sales_18w = Column(Integer, default=0)
    buyout_18w_pct = Column(Float, default=0.0)
    stock_wb = Column(Integer, default=0)
    stock_in_transit = Column(Integer, default=0)
    stock_days = Column(Float, default=0.0)
    stock_wb_prev = Column(Integer, default=0)
    avg_sales_per_week = Column(Float, default=0.0)
    turnover_days = Column(Float, default=0.0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
