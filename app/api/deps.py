import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.engine import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key_value
    if expected and not hmac.compare_digest(
        (x_api_key or "").encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="invalid api key")
