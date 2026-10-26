import base64
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "creator-live-ops"
    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "mysql+asyncmy://root:root@127.0.0.1:3306/ecom_ops?charset=utf8mb4"
    api_key: str = ""
    encryption_key: str = ""
    encryption_key_id: str = "k1"
    timezone: str = "Asia/Shanghai"
    warehouse_layout: Literal["single_db", "multi_schema"] = "single_db"
    warehouse_database: str = "ecom_ops"
    log_json: bool = False
    job_dir: str = "jobs"
    model_dir: str = "models"

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        if not value:
            return value
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("encryption_key must be valid base64") from exc
        if len(raw) != 32:
            raise ValueError("encryption_key must decode to 32 bytes")
        return value

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncmy", "+pymysql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
