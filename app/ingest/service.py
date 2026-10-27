import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import Table, func
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PermanentError, TimeWindow
from app.adapters.factory import AdapterFactory
from app.adapters.retry import retry_call
from app.core.settings import Settings
from app.db.models import EtlModelRun, EtlWatermark
from app.db.ods_models import (
    OdsAdCost,
    OdsAfterSale,
    OdsFetchLog,
    OdsLiveRoom,
    OdsOrder,
    OdsSettlement,
)
from app.scheduler.models import JobDefinition

PLATFORM_BY_ADAPTER = {
    "douyin_shop": "douyin",
    "douyin_qianchuan": "douyin",
    "csv_import": "douyin",
}
CHUNK_SIZE = 500


@dataclass(frozen=True)
class ResourceSpec:
    method: str
    table: type[Any]


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "orders": ResourceSpec("fetch_orders", OdsOrder),
    "after_sales": ResourceSpec("fetch_after_sales", OdsAfterSale),
    "settlements": ResourceSpec("fetch_settlements", OdsSettlement),
    "live_rooms": ResourceSpec("fetch_live_rooms", OdsLiveRoom),
    "ad_cost": ResourceSpec("fetch_ad_cost", OdsAdCost),
}


def build_upsert(table: Table, rows: list[dict[str, Any]]) -> Any:
    stmt = mysql_insert(table).values(rows)
    primary_keys = {column.name for column in table.primary_key.columns}
    updates: dict[str, Any] = {
        column.name: stmt.inserted[column.name]
        for column in table.columns
        if column.name not in primary_keys
        and column.name not in {"etl_create_at", "etl_update_at"}
    }
    updates["etl_update_at"] = func.now()
    return stmt.on_duplicate_key_update(**updates)


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._factory = adapter_factory or AdapterFactory(settings, session)

    async def run(
        self,
        job: JobDefinition,
        run_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        spec = RESOURCE_SPECS.get(job.resource)
        if spec is None:
            raise PermanentError(f"unsupported ingest resource: {job.resource}")

        window = TimeWindow(start_at, end_at)
        started = time.monotonic()
        attempts = 0
        platform = PLATFORM_BY_ADAPTER.get(job.adapter, "")
        rows: list[dict[str, Any]] = []
        try:
            async with asyncio.timeout(job.timeout_seconds):
                adapter = await self._factory.get(job.adapter)
                platform = adapter.platform or platform
                method = getattr(adapter, spec.method)

                async def call() -> list[dict[str, Any]]:
                    nonlocal attempts
                    attempts += 1
                    return await method(window)

                result = await retry_call(call, job.retry)
                rows = result.value
                await self._upsert(spec.table, rows, platform)
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_success(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                record_count=len(rows),
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
            )
            return len(rows)
        except TimeoutError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_failure(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
                error=f"timeout after {job.timeout_seconds}s",
            )
            raise TimeoutError(
                f"ingest timed out after {job.timeout_seconds}s"
            ) from exc
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_failure(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise
        finally:
            await self._factory.close()

    async def _upsert(
        self, table_type: type[Any], rows: list[dict[str, Any]], platform: str
    ) -> None:
        if not rows:
            return
        now = datetime.now(ZoneInfo(self._settings.timezone)).replace(tzinfo=None)
        batch_id = uuid4().hex
        table = table_type.__table__
        business_columns = [
            column.name
            for column in table.columns
            if column.name not in {"etl_create_at", "etl_update_at"}
        ]
        prepared: list[dict[str, Any]] = []
        for row in rows:
            record = {column: row.get(column) for column in business_columns}
            record["platform"] = row.get("platform") or platform
            record["batch_id"] = batch_id
            record["fetched_at"] = now
            prepared.append(record)
        for index in range(0, len(prepared), CHUNK_SIZE):
            chunk = prepared[index : index + CHUNK_SIZE]
            await self._session.execute(build_upsert(table, chunk))
        await self._session.commit()

    async def _record_success(
        self,
        *,
        job: JobDefinition,
        spec: ResourceSpec,
        run_id: int,
        window: TimeWindow,
        platform: str,
        record_count: int,
        retry_count: int,
        duration_ms: int,
    ) -> None:
        self._session.add(
            EtlModelRun(
                run_id=run_id,
                model_name=f"ingest:{job.resource}",
                target_table=spec.table.__tablename__,
                layer="ods",
                status="success",
                row_count=record_count,
                duration_ms=duration_ms,
            )
        )
        self._session.add(
            OdsFetchLog(
                platform=platform,
                resource=job.resource,
                window_start=window.start_at,
                window_end=window.end_at,
                status="success",
                record_count=record_count,
                retry_count=retry_count,
                duration_ms=duration_ms,
            )
        )
        await self._advance_watermark(job.resource, platform, window.end_at)
        await self._session.commit()

    async def _record_failure(
        self,
        *,
        job: JobDefinition,
        spec: ResourceSpec,
        run_id: int,
        window: TimeWindow,
        platform: str,
        retry_count: int,
        duration_ms: int,
        error: str,
    ) -> None:
        try:
            await self._session.rollback()
            self._session.add(
                EtlModelRun(
                    run_id=run_id,
                    model_name=f"ingest:{job.resource}",
                    target_table=spec.table.__tablename__,
                    layer="ods",
                    status="failed",
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            self._session.add(
                OdsFetchLog(
                    platform=platform,
                    resource=job.resource,
                    window_start=window.start_at,
                    window_end=window.end_at,
                    status="failed",
                    record_count=0,
                    retry_count=retry_count,
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            await self._session.commit()
        except Exception:
            logger.exception("failed to record ingest failure for {}", job.id)
            await self._session.rollback()

    async def _advance_watermark(
        self, resource: str, platform: str, end_at: datetime
    ) -> None:
        row = await self._session.get(EtlWatermark, (resource, platform))
        if row is None:
            self._session.add(
                EtlWatermark(
                    resource=resource,
                    platform=platform,
                    last_success_at=end_at,
                )
            )
        elif end_at > row.last_success_at:
            row.last_success_at = end_at
