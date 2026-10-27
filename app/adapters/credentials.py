from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretBox
from app.core.settings import Settings
from app.db.models import AuditSecretAccess, SysConfig


class CredentialResolver:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        actor: str = "ingest",
    ) -> None:
        self._session = session
        self._settings = settings
        self._actor = actor
        key = settings.encryption_key_value
        self._box = SecretBox(key, settings.encryption_key_id) if key else None

    def _env_value(self, key: str) -> str:
        if key == "douyin.app_key":
            return self._settings.douyin_app_key_value
        if key == "douyin.app_secret":
            return self._settings.douyin_app_secret_value
        if key == "douyin.access_token":
            return self._settings.douyin_access_token_value
        if key == "douyin.refresh_token":
            return self._settings.douyin_refresh_token_value
        if key == "douyin.shop_id":
            return self._settings.douyin_shop_id
        if key == "qianchuan.access_token":
            return self._settings.qianchuan_access_token_value
        if key == "qianchuan.advertiser_pairs":
            return self._settings.qianchuan_advertiser_pairs
        return ""

    async def get(self, key: str) -> str:
        env_value = self._env_value(key)
        if env_value:
            return env_value

        row = await self._session.get(SysConfig, key)
        if row is None or not row.config_value:
            return ""
        if not row.is_secret:
            return row.config_value
        if self._box is None:
            raise ValueError(f"encryption key is required to read {key}")
        plaintext = self._box.decrypt(row.config_value, aad=key)
        self._session.add(
            AuditSecretAccess(actor=self._actor, config_key=key, action="read")
        )
        await self._session.commit()
        return plaintext

    async def set_secret(self, key: str, value: str) -> None:
        if self._box is None:
            raise ValueError("encryption key is not configured")
        stored = self._box.encrypt(value, aad=key)
        row = await self._session.get(SysConfig, key)
        if row is None:
            row = SysConfig(config_key=key)
            self._session.add(row)
        row.config_value = stored
        row.is_secret = True
        row.key_id = self._box.key_id
        await self._session.commit()
