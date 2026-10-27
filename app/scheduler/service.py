from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import JobAlreadyRunning
from app.core.settings import Settings
from app.db.models import EtlRun
from app.scheduler.lanes import LaneManager
from app.scheduler.lock import JobLock
from app.scheduler.models import JobDefinition
from app.warehouse.parser import load_models
from app.warehouse.quality import QualityCheck, run_checks
from app.warehouse.renderer import TableRenderer
from app.warehouse.runner import PipelineRunner


class JobService:
    def __init__(self, session: AsyncSession, settings: Settings, owner: str) -> None:
        self._session = session
        self._settings = settings
        self._owner = owner

    def _now(self) -> datetime:
        return datetime.now(ZoneInfo(self._settings.timezone)).replace(tzinfo=None)

    async def run(
        self,
        job: JobDefinition,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        lock = JobLock(
            self._session,
            owner=self._owner,
            ttl_seconds=max(job.timeout_seconds, 60) + 60,
        )
        if not await lock.acquire(job.id):
            raise JobAlreadyRunning(job.id)

        try:
            run = EtlRun(
                job_id=job.id,
                window_start=start_at,
                window_end=end_at,
                status="running",
            )
            self._session.add(run)
            await self._session.commit()
            await self._session.refresh(run)

            renderer = TableRenderer(self._settings.warehouse_layout)
            models = load_models(Path(self._settings.model_dir))
            quality_checks: list[QualityCheck] = []
            if (
                self._settings.warehouse_layout == "single_db"
                and "ads_demo_talent_daily" in models
            ):
                quality_checks.append(
                    QualityCheck(
                        model_name="ads_demo_talent_daily",
                        test_name="gmv_not_null",
                        sql=(
                            "SELECT COUNT(*) FROM "
                            f"{renderer.ref('ads_demo_talent_daily')} WHERE gmv IS NULL"
                        ),
                    )
                )
            runner = PipelineRunner(
                self._session,
                self._settings.model_dir,
                renderer,
            )
            try:
                await runner.run(run.id, start_at, end_at)
                quality = (
                    await run_checks(self._session, run.id, quality_checks)
                    if quality_checks
                    else []
                )
                if any(item.status == "failed" for item in quality):
                    raise RuntimeError("quality checks failed")
                run.status = "success"
                run.finished_at = self._now()
                await self._session.commit()
            except Exception as exc:
                run.status = "failed"
                run.error = str(exc)
                run.finished_at = self._now()
                await self._session.commit()
                raise
            return run.id
        finally:
            try:
                await lock.release(job.id)
            except Exception:
                logger.exception("failed to release lock for job {}", job.id)


class SchedulerService:
    def __init__(
        self,
        jobs: dict[str, JobDefinition],
        lanes: LaneManager,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._jobs = jobs
        self._lanes = lanes
        self._session_factory = session_factory
        self._settings = settings
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)

    def start(self) -> None:
        for job in self._jobs.values():
            if not job.enabled:
                continue
            self._scheduler.add_job(
                self._run_job,
                CronTrigger.from_crontab(job.schedule, timezone=self._settings.timezone),
                args=[job.id],
                id=job.id,
                replace_existing=True,
            )
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def _run_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        start_at, end_at = default_window(job.window, tz=self._settings.timezone)
        async with self._lanes.semaphore(job.lane):
            async with self._session_factory() as session:
                service = JobService(
                    session,
                    self._settings,
                    owner=f"scheduler:{job_id}:{uuid4().hex}",
                )
                await service.run(job, start_at, end_at)


def default_window(
    kind: str,
    now: datetime | None = None,
    tz: str = "Asia/Shanghai",
) -> tuple[datetime, datetime]:
    current = now or datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    today = current.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "day":
        return today - timedelta(days=1), today
    if kind == "hour":
        current_hour = current.replace(minute=0, second=0, microsecond=0)
        return current_hour - timedelta(hours=1), current_hour
    if kind == "minute":
        current_minute = current.replace(second=0, microsecond=0)
        return current_minute - timedelta(minutes=1), current_minute
    raise ValueError(f"unsupported window: {kind}")
