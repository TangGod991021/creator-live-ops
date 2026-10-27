from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class OdsOrder(Base):
    __tablename__ = "ods_order"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str | None] = mapped_column(String(64))
    order_status: Mapped[str | None] = mapped_column(String(40))
    pay_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pay_at: Mapped[datetime | None] = mapped_column(DateTime)
    create_at: Mapped[datetime | None] = mapped_column(DateTime)
    update_at: Mapped[datetime | None] = mapped_column(DateTime)
    talent_id: Mapped[str | None] = mapped_column(String(64))
    room_id: Mapped[str | None] = mapped_column(String(64))
    channel_type: Mapped[str | None] = mapped_column(String(40))
    content_type: Mapped[str | None] = mapped_column(String(40))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsAfterSale(Base):
    __tablename__ = "ods_after_sale"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    after_sale_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str | None] = mapped_column(String(40))
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    apply_at: Mapped[datetime | None] = mapped_column(DateTime)
    finish_at: Mapped[datetime | None] = mapped_column(DateTime)
    update_at: Mapped[datetime | None] = mapped_column(DateTime)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsSettlement(Base):
    __tablename__ = "ods_settlement"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    settlement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(64))
    settle_at: Mapped[datetime | None] = mapped_column(DateTime)
    settle_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    talent_commission: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    service_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsLiveRoom(Base):
    __tablename__ = "ods_live_room"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str | None] = mapped_column(String(64))
    talent_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str | None] = mapped_column(String(40))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsAdCost(Base):
    __tablename__ = "ods_ad_cost"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stat_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    granularity: Mapped[str] = mapped_column(String(10), primary_key=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    conversions: Mapped[int | None] = mapped_column(BigInteger)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsFetchLog(Base):
    __tablename__ = "ods_fetch_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ods_fetch_log_resource_created", "resource", "created_at"),
    )
