import base64

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_valid_encryption_key() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    settings = Settings(_env_file=None, encryption_key=key)
    assert settings.encryption_key == key


def test_encryption_key_must_be_32_bytes() -> None:
    key = base64.b64encode(b"short").decode()
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None, encryption_key=key)


def test_sync_database_url_replaces_driver() -> None:
    settings = Settings(
        _env_file=None,
        database_url="mysql+asyncmy://u:p@h:3306/db?charset=utf8mb4",
    )
    assert settings.sync_database_url == "mysql+pymysql://u:p@h:3306/db?charset=utf8mb4"
