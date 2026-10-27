from app.adapters.base import PermanentError
from app.adapters.csv.adapter import CsvImportAdapter
from app.adapters.douyin.adapter import DouyinShopAdapter
from app.adapters.factory import AdapterFactory
from app.adapters.qianchuan.adapter import QianchuanAdapter
from app.core.settings import Settings


class FakeSession:
    def __init__(self) -> None:
        self.rows = {}

    async def get(self, model, key):
        return self.rows.get(key)

    def add(self, row) -> None:
        return None

    async def commit(self) -> None:
        return None


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


async def test_builds_douyin_shop_adapter() -> None:
    settings = make_settings(
        douyin_app_key="key",
        douyin_app_secret="secret",
        douyin_access_token="token",
    )
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("douyin_shop")
    assert isinstance(adapter, DouyinShopAdapter)
    await factory.close()


async def test_builds_qianchuan_adapter() -> None:
    settings = make_settings(
        qianchuan_access_token="token",
        qianchuan_advertiser_pairs="1:2,3:4",
    )
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("douyin_qianchuan")
    assert isinstance(adapter, QianchuanAdapter)
    await factory.close()


async def test_builds_csv_adapter(tmp_path) -> None:
    settings = make_settings(
        csv_import_dir=str(tmp_path),
        csv_mappings_dir="app/adapters/csv/mappings",
    )
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("csv_import")
    assert isinstance(adapter, CsvImportAdapter)
    await factory.close()


async def test_unknown_adapter_is_rejected() -> None:
    factory = AdapterFactory(make_settings(), FakeSession())
    try:
        await factory.get("nope")
    except PermanentError as exc:
        assert "unknown adapter" in str(exc)
    else:
        raise AssertionError("expected unknown adapter error")
