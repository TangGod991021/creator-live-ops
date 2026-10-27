from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, require_api_key
from app.core.response import ok
from app.core.settings import get_settings
from app.scheduler.loader import load_jobs
from app.scheduler.models import JobDefinition
from app.scheduler.service import JobService, default_window

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_api_key)],
)


def _serialize(job: JobDefinition) -> dict:
    return {
        "id": job.id,
        "lane": job.lane,
        "schedule": job.schedule,
        "resource": job.resource,
        "window": job.window,
        "depends_on": list(job.depends_on),
        "enabled": job.enabled,
    }


@router.get("")
async def list_jobs() -> dict:
    jobs = load_jobs(Path(get_settings().job_dir))
    return ok([_serialize(job) for job in jobs.values()])


@router.post("/{job_id}/run")
async def run_job(job_id: str, session: SessionDep) -> dict:
    settings = get_settings()
    jobs = load_jobs(Path(settings.job_dir))
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    start_at, end_at = default_window(job.window, tz=settings.timezone)
    service = JobService(session, settings, owner=f"api:{uuid4().hex}")
    run_id = await service.run(job, start_at, end_at)
    return ok({"run_id": run_id, "job_id": job_id})
