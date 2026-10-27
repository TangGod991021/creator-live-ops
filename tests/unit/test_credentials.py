import base64

import pytest

from app.adapters.credentials import CredentialResolver
from app.core.crypto import SecretBox
from app.core.settings import Settings
from app.db.models import AuditSecretAccess, SysConfig


class FakeSession:
    def __init__(self) -> None:
        self.rows: dict[str, SysConfig] = {}
        self.added: list[object] = []
        self.audits: list[AuditSecretAccess] = []
        self.commits = 0

    async def get(self, model, key):
        assert model is SysConfig
        return self.rows.get(key)

    def add(self, row: object) -> None:
        self.added.append(row)
        if isinstance(row, AuditSecretAccess):
            self.audits.append(row)

    async def commit(self) -> None:
        self.commits += 1
        for row in self.added:
            if isinstance(row, SysConfig):
                self.rows[row.config_key] = row
        self.added.clear()


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


async def test_env_value_takes_precedence_over_database() -> None:
    session = FakeSession()
    row = SysConfig(
        config_key="douyin.app_key", config_value="from-db", is_secret=False
    )
    session.rows["douyin.app_key"] = row
    settings = make_settings(douyin_app_key="from-env")
    resolver = CredentialResolver(session, settings)
    assert await resolver.get("douyin.app_key") == "from-env"
    assert session.added == []


async def test_database_secret_is_decrypted_and_audited() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    box = SecretBox(key, "k1")
    session = FakeSession()
    session.rows["douyin.access_token"] = SysConfig(
        config_key="douyin.access_token",
        config_value=box.encrypt("token-value", aad="douyin.access_token"),
        is_secret=True,
        key_id="k1",
    )
    settings = make_settings(encryption_key=key)
    resolver = CredentialResolver(session, settings)
    assert await resolver.get("douyin.access_token") == "token-value"
    assert len(session.audits) == 1
    assert session.audits[0].config_key == "douyin.access_token"


async def test_set_secret_encrypts_and_persists() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    session = FakeSession()
    settings = make_settings(encryption_key=key)
    resolver = CredentialResolver(session, settings)
    await resolver.set_secret("douyin.refresh_token", "refresh-value")
    row = session.rows["douyin.refresh_token"]
    assert row.is_secret is True
    assert row.key_id == "k1"
    assert row.config_value != "refresh-value"
    assert (
        box_decrypt(settings, row.config_value, "douyin.refresh_token")
        == "refresh-value"
    )


def box_decrypt(settings: Settings, token: str, key: str) -> str:
    box = SecretBox(settings.encryption_key_value, settings.encryption_key_id)
    return box.decrypt(token, aad=key)


async def test_set_secret_requires_encryption_key() -> None:
    resolver = CredentialResolver(FakeSession(), make_settings())
    with pytest.raises(ValueError, match="encryption key"):
        await resolver.set_secret("douyin.refresh_token", "value")
