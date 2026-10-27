from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import SessionDep, require_api_key
from app.core.crypto import SecretBox
from app.core.response import ok
from app.core.settings import get_settings
from app.services.config_service import ConfigService

router = APIRouter(
    prefix="/api/v1/config",
    tags=["config"],
    dependencies=[Depends(require_api_key)],
)


class ConfigUpdate(BaseModel):
    value: str
    is_secret: bool = False


def _box() -> SecretBox | None:
    settings = get_settings()
    key = settings.encryption_key_value
    if not key:
        return None
    return SecretBox(key, settings.encryption_key_id)


@router.get("")
async def list_config(session: SessionDep) -> dict:
    service = ConfigService(session, _box())
    return ok(await service.list())


@router.put("/{key}")
async def set_config(key: str, body: ConfigUpdate, session: SessionDep) -> dict:
    try:
        service = ConfigService(session, _box())
        await service.set(key, body.value, body.is_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"key": key})
