from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class OdsDemoOrder(Base):
    __tablename__ = "ods_demo_order"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pay_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    pay_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    talent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    room_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DwdDemoOrder(Base):
    __tablename__ = "dwd_demo_order"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pay_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    talent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    room_id: Mapped[str] = mapped_column(String(64), nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DwsDemoTalentDaily(Base):
    __tablename__ = "dws_demo_talent_daily"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    talent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stat_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gmv: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    order_count: Mapped[int] = mapped_column(nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AdsDemoTalentDaily(Base):
    __tablename__ = "ads_demo_talent_daily"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    talent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stat_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gmv: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    order_count: Mapped[int] = mapped_column(nullable=False)
    rank_no: Mapped[int] = mapped_column(nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
