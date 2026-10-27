from app.adapters.douyin.token import DouyinTokenProvider


class FakeResolver:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.writes: list[tuple[str, str]] = []

    async def get(self, key: str) -> str:
        return self.data.get(key, "")

    async def set_secret(self, key: str, value: str) -> None:
        self.data[key] = value
        self.writes.append((key, value))


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict, bool]] = []
        self.access_token = ""

    async def request(self, method, params=None, *, include_access_token=True):
        self.calls.append((method, params or {}, include_access_token))
        return self.responses.pop(0)


async def test_get_access_token_creates_when_missing() -> None:
    resolver = FakeResolver()
    client = FakeClient(
        [{"access_token": "new-token", "refresh_token": "new-refresh"}]
    )
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.get_access_token() == "new-token"
    assert resolver.data["douyin.access_token"] == "new-token"
    assert resolver.data["douyin.refresh_token"] == "new-refresh"
    assert client.calls[0][0] == "token.create"
    assert client.calls[0][2] is False


async def test_get_access_token_reuses_existing() -> None:
    resolver = FakeResolver()
    resolver.data["douyin.access_token"] = "existing"
    client = FakeClient([])
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.get_access_token() == "existing"
    assert client.calls == []


async def test_refresh_uses_refresh_token() -> None:
    resolver = FakeResolver()
    resolver.data["douyin.refresh_token"] = "old-refresh"
    client = FakeClient(
        [{"access_token": "fresh", "refresh_token": "fresh-refresh"}]
    )
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.refresh() == "fresh"
    assert client.calls[0][0] == "token.refresh"
    assert client.calls[0][1] == {
        "refresh_token": "old-refresh",
        "grant_type": "refresh_token",
    }
    assert resolver.data["douyin.access_token"] == "fresh"
