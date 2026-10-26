import base64

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_valid_encryption_key() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    settings = Settings(_env_file=None, encryption_key=key)
    assert settings.encryption_key.get_secret_value() == key


def test_empty_encryption_key_allowed_in_dev() -> None:
    settings = Settings(_env_file=None, encryption_key="")
    assert settings.encryption_key.get_secret_value() == ""


def test_encryption_key_must_be_32_bytes() -> None:
    key = base64.b64encode(b"short").decode()
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None, encryption_key=key)


def test_encryption_key_must_be_valid_base64() -> None:
    with pytest.raises(ValidationError, match="valid base64"):
        Settings(_env_file=None, encryption_key="not-base64!")


def test_sync_database_url_replaces_driver_only_in_scheme() -> None:
    settings = Settings(
        _env_file=None,
        database_url="mysql+asyncmy://u:p+asyncmy@h:3306/db?charset=utf8mb4",
    )
    assert (
        settings.sync_database_url
        == "mysql+pymysql://u:p+asyncmy@h:3306/db?charset=utf8mb4"
    )


def test_sync_database_url_requires_asyncmy_scheme() -> None:
    settings = Settings(_env_file=None, database_url="mysql+pymysql://u:p@h:3306/db")
    with pytest.raises(ValueError, match=r"mysql\+asyncmy"):
        _ = settings.sync_database_url


def test_prod_requires_encryption_key() -> None:
    with pytest.raises(ValidationError, match="encryption_key is required in prod"):
        Settings(_env_file=None, env="prod", api_key="strong-random-key")


def test_prod_requires_changed_api_key() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    with pytest.raises(ValidationError, match="api_key must be changed in prod"):
        Settings(_env_file=None, env="prod", api_key="change-me", encryption_key=key)


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Settings(_env_file=None, timezone="Not/AZone")
