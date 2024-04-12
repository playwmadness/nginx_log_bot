import aiohttp

from .db import DB_COLUMNS, Db


class IpInfo:
    def __init__(self, api_key: str, *, api_url: str = "https://ipinfo.io"):
        self._db = Db()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        self._session = aiohttp.ClientSession(
            api_url,
            headers=headers,
        )

    async def __aenter__(self) -> "IpInfo":
        return self

    async def __aexit__(self, *_) -> None:
        await self._session.close()

    async def find_ip(self, ip: str) -> dict:
        if info := self._db.find_ip(ip):
            return info

        async with self._session.get(f"/{ip}") as response:
            if response.status == 200:
                info = await response.json()
            else:
                raise RuntimeError(f"Query failed: {response}")

        self._db.save_ipinfo(info)
        return {key: info.get(key, "") for key in DB_COLUMNS.keys()}
