import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.settings import get_settings
from app.db.engine import get_session_factory
from app.scheduler.loader import load_jobs
from app.scheduler.service import JobService, default_window


async def run_job(
    job_id: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> int:
    settings = get_settings()
    jobs = load_jobs(Path(settings.job_dir))
    job = jobs[job_id]
    if (start_at is None) != (end_at is None):
        raise ValueError("start_at and end_at must be provided together")
    if start_at is None or end_at is None:
        start_at, end_at = default_window(job.window, tz=settings.timezone)
    async with get_session_factory()() as session:
        service = JobService(session, settings, owner=f"cli:{uuid4().hex}")
        return await service.run(job, start_at, end_at)


async def run_demo(job_id: str = "demo_pipeline") -> int:
    return await run_job(job_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="demo_pipeline")
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    start_at = datetime.fromisoformat(args.start) if args.start else None
    end_at = datetime.fromisoformat(args.end) if args.end else None
    run_id = asyncio.run(run_job(args.job, start_at, end_at))
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
