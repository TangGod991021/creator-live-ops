import base64
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "creator-live-ops"
    env: Literal["dev", "test", "prod"] = "dev"
    database_url: SecretStr = SecretStr(
        "mysql+asyncmy://root:root@127.0.0.1:3306/ecom_ops?charset=utf8mb4"
    )
    api_key: SecretStr = SecretStr("")
    encryption_key: SecretStr = SecretStr("")
    encryption_key_id: str = "k1"
    timezone: str = "Asia/Shanghai"
    warehouse_layout: Literal["single_db", "multi_schema"] = "single_db"
    warehouse_database: str = "ecom_ops"
    log_json: bool = False
    enable_scheduler: bool = False
    job_dir: str = "jobs"
    model_dir: str = "models"
    metrics_file: str = "metrics/metrics.yml"
    douyin_app_key: SecretStr = SecretStr("")
    douyin_app_secret: SecretStr = SecretStr("")
    douyin_access_token: SecretStr = SecretStr("")
    douyin_refresh_token: SecretStr = SecretStr("")
    douyin_shop_id: str = ""
    douyin_base_url: str = "https://openapi-fxg.jinritemai.com"
    qianchuan_access_token: SecretStr = SecretStr("")
    qianchuan_advertiser_pairs: str = ""
    qianchuan_base_url: str = "https://api.oceanengine.com/open_api"
    csv_import_dir: str = "data/csv"
    csv_mappings_dir: str = "app/adapters/csv/mappings"
    http_timeout_seconds: float = 20.0

    @field_validator("encryption_key", mode="before")
    @classmethod
    def validate_encryption_key(cls, value: str | SecretStr) -> str | SecretStr:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not raw_value:
            return value
        try:
            raw = base64.b64decode(raw_value, validate=True)
        except Exception as exc:
            raise ValueError("encryption_key must be valid base64") from exc
        if len(raw) != 32:
            raise ValueError("encryption_key must decode to 32 bytes")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def validate_prod_secrets(self) -> "Settings":
        if self.env == "prod":
            if not self.encryption_key.get_secret_value():
                raise ValueError("encryption_key is required in prod")
            if self.api_key.get_secret_value() in {"", "change-me"}:
                raise ValueError("api_key must be changed in prod")
        return self

    @property
    def database_url_value(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def api_key_value(self) -> str:
        return self.api_key.get_secret_value()

    @property
    def encryption_key_value(self) -> str:
        return self.encryption_key.get_secret_value()

    @property
    def douyin_app_key_value(self) -> str:
        return self.douyin_app_key.get_secret_value()

    @property
    def douyin_app_secret_value(self) -> str:
        return self.douyin_app_secret.get_secret_value()

    @property
    def douyin_access_token_value(self) -> str:
        return self.douyin_access_token.get_secret_value()

    @property
    def douyin_refresh_token_value(self) -> str:
        return self.douyin_refresh_token.get_secret_value()

    @property
    def qianchuan_access_token_value(self) -> str:
        return self.qianchuan_access_token.get_secret_value()

    @property
    def sync_database_url(self) -> str:
        prefix = "mysql+asyncmy:"
        url = self.database_url_value
        if not url.startswith(prefix):
            raise ValueError("database_url must start with mysql+asyncmy:")
        return "mysql+pymysql:" + url[len(prefix) :]


@lru_cache
def get_settings() -> Settings:
    return Settings()
