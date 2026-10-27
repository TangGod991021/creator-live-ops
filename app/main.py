from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api import catalog, config, health, jobs, runs
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_json)
    if settings.enable_scheduler:
        from pathlib import Path

        from app.db.engine import get_session_factory
        from app.scheduler.lanes import LaneManager
        from app.scheduler.loader import load_jobs
        from app.scheduler.service import SchedulerService

        scheduler = SchedulerService(
            jobs=load_jobs(Path(settings.job_dir)),
            lanes=LaneManager({"demo": 1, "csv_import": 2}),
            session_factory=get_session_factory(),
            settings=settings,
        )
        scheduler.start()
        app.state.scheduler = scheduler
    yield
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": str(exc), "data": None},
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": str(exc.detail),
                "data": None,
            },
        )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(runs.router)
    app.include_router(config.router)
    app.include_router(catalog.router)
    return app


app = create_app()
