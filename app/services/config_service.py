from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretBox
from app.db.models import SysConfig


class ConfigService:
    def __init__(self, session: AsyncSession, box: SecretBox | None) -> None:
        self._session = session
        self._box = box

    async def list(self) -> list[dict]:
        rows = (await self._session.execute(select(SysConfig))).scalars().all()
        return [
            {
                "key": row.config_key,
                "value": "***" if row.is_secret else row.config_value,
                "is_secret": row.is_secret,
            }
            for row in rows
        ]

    async def set(self, key: str, value: str, is_secret: bool) -> None:
        if is_secret:
            if self._box is None:
                raise ValueError("encryption key is not configured")
            stored = self._box.encrypt(value, aad=key)
            key_id = self._box.key_id
        else:
            stored = value
            key_id = None
        row = await self._session.get(SysConfig, key)
        if row is None:
            row = SysConfig(
                config_key=key,
                config_value=stored,
                is_secret=is_secret,
                key_id=key_id,
            )
            self._session.add(row)
        else:
            row.config_value = stored
            row.is_secret = is_secret
            row.key_id = key_id
        await self._session.commit()
