from app.adapters.base import AuthError
from app.adapters.credentials import CredentialResolver
from app.adapters.douyin.client import DouyinClient

ACCESS_TOKEN_KEY = "douyin.access_token"
REFRESH_TOKEN_KEY = "douyin.refresh_token"


class DouyinTokenProvider:
    def __init__(self, client: DouyinClient, resolver: CredentialResolver) -> None:
        self._client = client
        self._resolver = resolver

    async def get_access_token(self) -> str:
        token = await self._resolver.get(ACCESS_TOKEN_KEY)
        if token:
            return token
        return await self._create()

    async def refresh(self) -> str:
        refresh_token = await self._resolver.get(REFRESH_TOKEN_KEY)
        if not refresh_token:
            return await self._create()
        data = await self._client.request(
            "token.refresh",
            {"refresh_token": refresh_token, "grant_type": "refresh_token"},
            include_access_token=False,
        )
        return await self._store(data)

    async def _create(self) -> str:
        data = await self._client.request(
            "token.create",
            {"code": "", "grant_type": "authorization_self"},
            include_access_token=False,
        )
        return await self._store(data)

    async def _store(self, data: dict) -> str:
        token = str(data.get("access_token") or "")
        if not token:
            raise AuthError("douyin token response missing access_token")
        await self._resolver.set_secret(ACCESS_TOKEN_KEY, token)
        refresh_token = data.get("refresh_token")
        if refresh_token:
            await self._resolver.set_secret(REFRESH_TOKEN_KEY, str(refresh_token))
        return token
