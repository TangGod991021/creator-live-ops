"""demo tables

Revision ID: 0002_demo_tables
Revises: 0001_system_tables
Create Date: 2026-10-26
"""
import sqlalchemy as sa

from alembic import op

revision = "0002_demo_tables"
down_revision = "0001_system_tables"
branch_labels = None
depends_on = None

TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    op.create_table(
        "ods_demo_order",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("pay_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("pay_at", sa.DateTime(), nullable=False),
        sa.Column("talent_id", sa.String(64), nullable=False),
        sa.Column("room_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )
    op.create_table(
        "dwd_demo_order",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("pay_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("talent_id", sa.String(64), nullable=False),
        sa.Column("room_id", sa.String(64), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )
    op.create_index("ix_dwd_demo_order_stat_date", "dwd_demo_order", ["stat_date"])
    op.create_table(
        "dws_demo_talent_daily",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("talent_id", sa.String(64), primary_key=True),
        sa.Column("stat_date", sa.Date(), primary_key=True),
        sa.Column("gmv", sa.Numeric(18, 2), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )
    op.create_table(
        "ads_demo_talent_daily",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("talent_id", sa.String(64), primary_key=True),
        sa.Column("stat_date", sa.Date(), primary_key=True),
        sa.Column("gmv", sa.Numeric(18, 2), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("rank_no", sa.Integer(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )


def downgrade() -> None:
    op.drop_index("ix_dwd_demo_order_stat_date", table_name="dwd_demo_order")
    for table in [
        "ads_demo_talent_daily",
        "dws_demo_talent_daily",
        "dwd_demo_order",
        "ods_demo_order",
    ]:
        op.drop_table(table)
