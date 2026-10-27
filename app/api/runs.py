from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, require_api_key
from app.core.response import ok
from app.db.models import EtlModelRun, EtlRun

router = APIRouter(
    prefix="/api/v1/runs",
    tags=["runs"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
async def list_runs(session: SessionDep, limit: int = 50) -> dict:
    rows = (
        (await session.execute(select(EtlRun).order_by(EtlRun.id.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": row.id,
                "job_id": row.job_id,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "error": row.error,
            }
            for row in rows
        ]
    )


@router.get("/{run_id}")
async def get_run(run_id: int, session: SessionDep) -> dict:
    run = await session.get(EtlRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    models = (
        (await session.execute(select(EtlModelRun).where(EtlModelRun.run_id == run_id)))
        .scalars()
        .all()
    )
    return ok(
        {
            "id": run.id,
            "job_id": run.job_id,
            "status": run.status,
            "error": run.error,
            "models": [
                {
                    "model": row.model_name,
                    "layer": row.layer,
                    "status": row.status,
                    "row_count": row.row_count,
                    "duration_ms": row.duration_ms,
                }
                for row in models
            ],
        }
    )
