"""add_monthly_plans

Revision ID: 437bceeccdd8
Revises: ad76df06830b
Create Date: 2026-05-05

Таблица monthly_plans — план магазина на месяц (один план на месяц для всего магазина).
Используется на странице «План/Факт» как источник плановых значений.
"""
from alembic import op
import sqlalchemy as sa


revision = '437bceeccdd8'
down_revision = 'ad76df06830b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'monthly_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('month', sa.Date(), nullable=False, unique=True),
        sa.Column('plan_orders_qty', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('plan_orders_revenue', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('plan_buyouts_qty', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('plan_buyouts_revenue', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('plan_margin', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_monthly_plans_month', 'monthly_plans', [sa.text('month DESC')])


def downgrade() -> None:
    op.drop_index('idx_monthly_plans_month', table_name='monthly_plans')
    op.drop_table('monthly_plans')
