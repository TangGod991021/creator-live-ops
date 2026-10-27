from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter, PermanentError
from app.adapters.credentials import CredentialResolver
from app.adapters.csv.adapter import CsvImportAdapter
from app.adapters.douyin.adapter import DouyinShopAdapter
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.token import DouyinTokenProvider
from app.adapters.qianchuan.adapter import QianchuanAdapter, parse_advertiser_pairs
from app.adapters.qianchuan.client import QianchuanClient
from app.core.settings import Settings


class AdapterFactory:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        self._settings = settings
        self._resolver = CredentialResolver(session, settings)
        self._cache: dict[str, BaseAdapter] = {}

    async def get(self, name: str) -> BaseAdapter:
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        if name == "douyin_shop":
            adapter: BaseAdapter = await self._douyin_shop()
        elif name == "douyin_qianchuan":
            adapter = await self._qianchuan()
        elif name == "csv_import":
            adapter = CsvImportAdapter(
                self._settings.csv_import_dir,
                self._settings.csv_mappings_dir,
            )
        else:
            raise PermanentError(f"unknown adapter: {name}")
        self._cache[name] = adapter
        return adapter

    async def _douyin_shop(self) -> DouyinShopAdapter:
        token = await self._resolver.get("douyin.access_token")
        client = DouyinClient(
            app_key=await self._resolver.get("douyin.app_key"),
            app_secret=await self._resolver.get("douyin.app_secret"),
            access_token=token,
            base_url=self._settings.douyin_base_url,
            timeout=self._settings.http_timeout_seconds,
        )
        provider = DouyinTokenProvider(client, self._resolver)
        return DouyinShopAdapter(client, provider)

    async def _qianchuan(self) -> QianchuanAdapter:
        token = await self._resolver.get("qianchuan.access_token")
        pairs = parse_advertiser_pairs(
            await self._resolver.get("qianchuan.advertiser_pairs")
        )
        client = QianchuanClient(
            access_token=token,
            base_url=self._settings.qianchuan_base_url,
            timeout=self._settings.http_timeout_seconds,
        )
        return QianchuanAdapter(client, pairs)

    async def close(self) -> None:
        for adapter in self._cache.values():
            await adapter.close()
        self._cache.clear()
