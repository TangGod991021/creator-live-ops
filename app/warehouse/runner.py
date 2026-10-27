import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EtlModelRun
from app.warehouse.dag import topological_order
from app.warehouse.model import SqlModel
from app.warehouse.parser import load_models
from app.warehouse.renderer import TableRenderer, render_sql


class PipelineRunner:
    def __init__(
        self,
        session: AsyncSession,
        model_dir: str,
        renderer: TableRenderer,
    ) -> None:
        self._session = session
        self._model_dir = model_dir
        self._renderer = renderer

    async def run(self, run_id: int, start_at: datetime, end_at: datetime) -> None:
        models = load_models(Path(self._model_dir))
        for name in topological_order(models):
            await self._run_model(run_id, models[name], start_at, end_at)

    async def _run_model(
        self,
        run_id: int,
        model: SqlModel,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        sql = render_sql(model.sql, self._renderer, start_at, end_at)
        started = time.monotonic()
        try:
            result = await self._session.execute(text(sql))
            duration_ms = int((time.monotonic() - started) * 1000)
            self._session.add(
                EtlModelRun(
                    run_id=run_id,
                    model_name=model.target,
                    target_table=model.target,
                    layer=model.layer,
                    status="success",
                    row_count=getattr(result, "rowcount", None),
                    duration_ms=duration_ms,
                )
            )
            await self._session.commit()
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._session.rollback()
            self._session.add(
                EtlModelRun(
                    run_id=run_id,
                    model_name=model.target,
                    target_table=model.target,
                    layer=model.layer,
                    status="failed",
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            )
            await self._session.commit()
            raise
