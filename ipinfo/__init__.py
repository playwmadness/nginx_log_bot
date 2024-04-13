from datetime import MINYEAR, datetime

import aiohttp
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from .db_models import Access, Info, ip_to_int


class IpInfo:
    def __init__(
        self,
        api_key: str,
        db_engine: Engine,
        *,
        api_url: str = "https://ipinfo.io",
    ):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        self._http_session = aiohttp.ClientSession(
            api_url,
            headers=headers,
        )
        self._db_session = Session(db_engine)

    async def find(self, ip: str) -> Info:
        if entry := self._db_find(ip):
            return entry

        entry = await self._ipinfo_find(ip)

        self._db_session.add(entry)
        self._db_session.commit()

        return entry

    async def find_and_update(self, ip: str, accesses: list[Access]) -> Info:
        entry = self._db_find(ip) or await self._ipinfo_find(ip)

        entry.accesses.update(accesses)

        self._db_session.add(entry)
        self._db_session.commit()

        return entry

    def last_access(self) -> datetime:
        return self._db_session.scalar(func.max(Access.timestamp)) or datetime(
            MINYEAR, 1, 1
        )

    def _db_find(self, ip: str) -> Info | None:
        return self._db_session.scalar(select(Info).where(Info._ip == ip_to_int(ip)))

    async def _ipinfo_find(self, ip: str) -> Info:
        async with self._http_session.get(f"/{ip}") as response:
            if response.status == 200:
                json_info = await response.json()
            else:
                raise RuntimeError(f"Web query failed: {response}")
        return Info(
            ip=json_info["ip"],
            hostname=json_info.get("hostname"),
            org=json_info.get("org"),
            country=json_info.get("country"),
            region=json_info.get("region"),
            city=json_info.get("city"),
            postal=json_info.get("postal"),
            loc=json_info.get("loc"),
            timezone=json_info.get("timezone"),
        )

    async def __aenter__(self) -> "IpInfo":
        self._db_session.__enter__()
        await self._http_session.__aenter__()
        return self

    async def __aexit__(self, *args) -> None:
        await self._http_session.__aexit__(*args)
        self._db_session.__exit__(*args)
