"""
Модель monthly_plans — один план на месяц для всего магазина.

Используется на странице «План/Факт» как источник плановых значений.
ДРР в плане не задаётся — считается из факта (ad_spend / order_sum).
"""
from sqlalchemy import Column, Integer, Date, Numeric, DateTime, func
from app.database import Base


class MonthlyPlan(Base):
    __tablename__ = "monthly_plans"

    id = Column(Integer, primary_key=True)
    month = Column(Date, nullable=False, unique=True)  # первый день месяца, например 2026-05-01

    plan_orders_qty = Column(Integer, nullable=False, default=0)
    plan_orders_revenue = Column(Numeric(14, 2), nullable=False, default=0)
    plan_buyouts_qty = Column(Integer, nullable=False, default=0)
    plan_buyouts_revenue = Column(Numeric(14, 2), nullable=False, default=0)
    plan_margin = Column(Numeric(14, 2), nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
