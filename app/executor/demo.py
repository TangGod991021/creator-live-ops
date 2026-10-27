import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

from app.core.settings import get_settings
from app.db.engine import get_session_factory
from app.scheduler.loader import load_jobs
from app.scheduler.service import JobService, default_window


async def run_demo(job_id: str = "demo_pipeline") -> int:
    settings = get_settings()
    jobs = load_jobs(Path(settings.job_dir))
    job = jobs[job_id]
    start_at, end_at = default_window(job.window, tz=settings.timezone)
    async with get_session_factory()() as session:
        service = JobService(session, settings, owner=f"cli:{uuid4().hex}")
        return await service.run(job, start_at, end_at)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="demo_pipeline")
    args = parser.parse_args()
    run_id = asyncio.run(run_demo(args.job))
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
