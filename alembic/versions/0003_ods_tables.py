"""ods tables

Revision ID: 0003_ods_tables
Revises: 0002_demo_tables
Create Date: 2026-10-27
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_ods_tables"
down_revision = "0002_demo_tables"
branch_labels = None
depends_on = None

TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    op.create_table(
        "ods_order",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("shop_id", sa.String(64)),
        sa.Column("order_status", sa.String(40)),
        sa.Column("pay_amount", sa.Numeric(18, 2)),
        sa.Column("pay_at", sa.DateTime()),
        sa.Column("create_at", sa.DateTime()),
        sa.Column("update_at", sa.DateTime()),
        sa.Column("talent_id", sa.String(64)),
        sa.Column("room_id", sa.String(64)),
        sa.Column("channel_type", sa.String(40)),
        sa.Column("content_type", sa.String(40)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column(
            "etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index("ix_ods_order_pay_at", "ods_order", ["pay_at"])
    op.create_index("ix_ods_order_update_at", "ods_order", ["update_at"])

    op.create_table(
        "ods_after_sale",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("after_sale_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64)),
        sa.Column("type", sa.String(40)),
        sa.Column("status", sa.String(40)),
        sa.Column("refund_amount", sa.Numeric(18, 2)),
        sa.Column("apply_at", sa.DateTime()),
        sa.Column("finish_at", sa.DateTime()),
        sa.Column("update_at", sa.DateTime()),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column(
            "etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index("ix_ods_after_sale_order_id", "ods_after_sale", ["order_id"])
    op.create_index("ix_ods_after_sale_apply_at", "ods_after_sale", ["apply_at"])

    op.create_table(
        "ods_settlement",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("settlement_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64)),
        sa.Column("settle_at", sa.DateTime()),
        sa.Column("settle_amount", sa.Numeric(18, 2)),
        sa.Column("commission_amount", sa.Numeric(18, 2)),
        sa.Column("talent_commission", sa.Numeric(18, 2)),
        sa.Column("service_fee", sa.Numeric(18, 2)),
        sa.Column("platform_fee", sa.Numeric(18, 2)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column(
            "etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index("ix_ods_settlement_order_id", "ods_settlement", ["order_id"])
    op.create_index("ix_ods_settlement_settle_at", "ods_settlement", ["settle_at"])

    op.create_table(
        "ods_live_room",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("room_id", sa.String(64), primary_key=True),
        sa.Column("shop_id", sa.String(64)),
        sa.Column("talent_id", sa.String(64)),
        sa.Column("title", sa.String(255)),
        sa.Column("start_at", sa.DateTime()),
        sa.Column("end_at", sa.DateTime()),
        sa.Column("status", sa.String(40)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column(
            "etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index("ix_ods_live_room_start_at", "ods_live_room", ["start_at"])

    op.create_table(
        "ods_ad_cost",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("stat_time", sa.DateTime(), primary_key=True),
        sa.Column("granularity", sa.String(10), primary_key=True),
        sa.Column("cost", sa.Numeric(18, 2)),
        sa.Column("impressions", sa.BigInteger()),
        sa.Column("clicks", sa.BigInteger()),
        sa.Column("conversions", sa.BigInteger()),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column(
            "etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index("ix_ods_ad_cost_stat_time", "ods_ad_cost", ["stat_time"])

    op.create_table(
        "ods_fetch_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        **TABLE_KW,
    )
    op.create_index(
        "ix_ods_fetch_log_resource_created",
        "ods_fetch_log",
        ["resource", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ods_fetch_log_resource_created", table_name="ods_fetch_log")
    op.drop_index("ix_ods_ad_cost_stat_time", table_name="ods_ad_cost")
    op.drop_index("ix_ods_live_room_start_at", table_name="ods_live_room")
    op.drop_index("ix_ods_settlement_settle_at", table_name="ods_settlement")
    op.drop_index("ix_ods_settlement_order_id", table_name="ods_settlement")
    op.drop_index("ix_ods_after_sale_apply_at", table_name="ods_after_sale")
    op.drop_index("ix_ods_after_sale_order_id", table_name="ods_after_sale")
    op.drop_index("ix_ods_order_update_at", table_name="ods_order")
    op.drop_index("ix_ods_order_pay_at", table_name="ods_order")
    for table in [
        "ods_fetch_log",
        "ods_ad_cost",
        "ods_live_room",
        "ods_settlement",
        "ods_after_sale",
        "ods_order",
    ]:
        op.drop_table(table)
