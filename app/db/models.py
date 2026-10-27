from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SysConfig(Base):
    __tablename__ = "sys_config"

    config_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    config_value: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    key_id: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SysJobLock(Base):
    __tablename__ = "sys_job_lock"

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    lock_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EtlRun(Base):
    __tablename__ = "etl_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)


class EtlModelRun(Base):
    __tablename__ = "etl_model_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    layer: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class EtlQualityResult(Base):
    __tablename__ = "etl_quality_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    test_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)


class EtlWatermark(Base):
    __tablename__ = "etl_watermark"

    resource: Mapped[str] = mapped_column(String(100), primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_success_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuditSecretAccess(Base):
    __tablename__ = "audit_secret_access"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
