"""system tables

Revision ID: 0001_system_tables
Revises:
Create Date: 2026-10-26
"""
import sqlalchemy as sa

from alembic import op

revision = "0001_system_tables"
down_revision = None
branch_labels = None
depends_on = None

TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    op.create_table(
        "sys_config",
        sa.Column("config_key", sa.String(100), primary_key=True),
        sa.Column("config_value", sa.Text()),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("key_id", sa.String(20)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )
    op.create_table(
        "sys_job_lock",
        sa.Column("job_id", sa.String(100), primary_key=True),
        sa.Column("lock_owner", sa.String(100), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )
    op.create_table(
        "etl_run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(100), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("error", sa.Text()),
        **TABLE_KW,
    )
    op.create_index("ix_etl_run_job_id", "etl_run", ["job_id"])
    op.create_table(
        "etl_model_run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("target_table", sa.String(100), nullable=False),
        sa.Column("layer", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("row_count", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
        **TABLE_KW,
    )
    op.create_index("ix_etl_model_run_run_id", "etl_model_run", ["run_id"])
    op.create_table(
        "etl_quality_result",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("test_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("details", sa.Text()),
        **TABLE_KW,
    )
    op.create_index("ix_etl_quality_result_run_id", "etl_quality_result", ["run_id"])
    op.create_table(
        "etl_watermark",
        sa.Column("resource", sa.String(100), primary_key=True),
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=False),
        **TABLE_KW,
    )
    op.create_table(
        "audit_secret_access",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        **TABLE_KW,
    )


def downgrade() -> None:
    op.drop_index("ix_etl_quality_result_run_id", table_name="etl_quality_result")
    op.drop_index("ix_etl_model_run_run_id", table_name="etl_model_run")
    op.drop_index("ix_etl_run_job_id", table_name="etl_run")
    for table in [
        "audit_secret_access",
        "etl_watermark",
        "etl_quality_result",
        "etl_model_run",
        "etl_run",
        "sys_job_lock",
        "sys_config",
    ]:
        op.drop_table(table)
