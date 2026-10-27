from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.core.response import ok
from app.core.settings import get_settings
from app.warehouse.metrics import load_metrics
from app.warehouse.parser import load_models

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
async def catalog() -> dict:
    settings = get_settings()
    models = load_models(Path(settings.model_dir))
    metrics = load_metrics(Path(settings.metrics_file))
    return ok(
        {
            "models": [
                {
                    "name": model.target,
                    "layer": model.layer,
                    "depends_on": list(model.depends_on),
                    "window": model.window,
                }
                for model in models.values()
            ],
            "metrics": metrics,
        }
    )
