from sqlalchemy import Column, Integer, BigInteger, String, Float, Date, DateTime, UniqueConstraint, func
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nm_id = Column(BigInteger, unique=True, nullable=False, index=True)
    vendor_code = Column(String, default="")
    title = Column(String, default="")
    brand = Column(String, default="")
    subject_id = Column(Integer, default=0)
    subject_name = Column(String, default="")
    image_url = Column(String, default="")
    cost_price = Column(Float, default=0)
    plan_sales = Column(Integer, default=0)
    width_cm = Column(Float, default=0)
    height_cm = Column(Float, default=0)
    length_cm = Column(Float, default=0)
    weight_kg = Column(Float, default=0)
    volume_liters = Column(Float, default=0)
    warehouse_name = Column(String, default="")
    warehouse_coef = Column(Float, default=1.0)
    buyout_percent = Column(Float, default=0)
    avg_price_api = Column(Float, default=0)
    delivery_base_cost = Column(Float, default=0)
    return_logistics_cost = Column(Float, default=0)
    storage_cost_per_day = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProductDailyStat(Base):
    __tablename__ = "product_daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nm_id = Column(BigInteger, nullable=False, index=True)
    date = Column(Date, nullable=False)
    open_count = Column(Integer, default=0)
    cart_count = Column(Integer, default=0)
    order_count = Column(Integer, default=0)
    order_sum = Column(Float, default=0)
    buyout_count = Column(Integer, default=0)
    buyout_sum = Column(Float, default=0)
    buyout_percent = Column(Integer, default=0)
    cancel_count = Column(Integer, default=0)
    cancel_sum = Column(Float, default=0)
    avg_price_before_spp = Column(Float, default=0)
    avg_price_after_spp = Column(Float, default=0)
    avg_spp_pct = Column(Float, default=0)
    ad_views = Column(Integer, default=0)
    ad_clicks = Column(Integer, default=0)
    ad_ctr = Column(Float, default=0)
    ad_cpc = Column(Float, default=0)
    ad_spend = Column(Float, default=0)
    ad_atbs = Column(Integer, default=0)
    ad_orders = Column(Integer, default=0)
    delivery_cost = Column(Float, default=0)
    return_cost = Column(Float, default=0)
    storage_cost = Column(Float, default=0)
    commission_amount = Column(Float, default=0)
    commission_pct = Column(Float, default=0)
    cost_price_total = Column(Float, default=0)
    margin_profit = Column(Float, default=0)
    margin_profit_pct = Column(Float, default=0)
    margin_clean = Column(Float, default=0)
    margin_clean_pct = Column(Float, default=0)
    roi = Column(Float, default=0)
    profit_per_order = Column(Float, default=0)
    sizes_available = Column(Integer, default=0)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("nm_id", "date", name="uq_product_daily_stats_nm_date"),
    )


class ProductPlan(Base):
    __tablename__ = "product_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nm_id = Column(BigInteger, nullable=False, index=True)
    month = Column(String, nullable=False)
    plan_orders = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("nm_id", "month", name="uq_product_plans_nm_month"),
    )


class StockSnapshot(Base):
    __tablename__ = "stock_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nm_id = Column(BigInteger, nullable=False, index=True)
    warehouse_name = Column(String, default="")
    quantity = Column(Integer, default=0)
    in_way_to_client = Column(Integer, default=0)
    sizes_count = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now())
