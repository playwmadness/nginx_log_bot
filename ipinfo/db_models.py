from datetime import datetime
from typing import Set

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def ip_to_int(ip: str) -> int:
    res = 0
    for v in ip.split("."):
        res <<= 8
        res += int(v)
    return res


def int_to_ip(val: int) -> str:
    return f"{(val >> 24) & 0xFF}.{(val >> 16) & 0xFF}.{(val >> 8) & 0xFF}.{val & 0xFF}"


class Base(DeclarativeBase):
    pass


class Info(Base):
    __tablename__ = "ip_info"

    _ip: Mapped[int] = mapped_column(primary_key=True)

    @hybrid_property
    def ip(self) -> str:
        return int_to_ip(self._ip)

    @ip.inplace.setter  # pyright: ignore
    def _ip_setter(self, ip: str) -> None:
        self._ip = ip_to_int(ip)

    @ip.inplace.expression  # pyright: ignore
    @classmethod
    def _ip_expression(cls):
        return cls._ip

    hostname = Column(String(256))
    org = Column(String(256))
    country = Column(String(128))
    region = Column(String(128))
    city = Column(String(128))
    postal = Column(String(32))
    loc = Column(String(32))
    timezone = Column(String(32))

    accesses: Mapped[Set["Access"]] = relationship(
        back_populates="host",
        cascade="all, delete",
        passive_deletes=True,
    )

    def _format_access_times(self, older: int = 1, newer: int = 2) -> str:
        accs = list(sorted(map(lambda x: x.timestamp, self.accesses)))
        if len(accs) <= (older + 1 + newer):
            return "\n".join(map(str, accs))
        else:
            old = "\n".join(map(str, accs[:older]))
            new = "\n".join(map(str, accs[-newer:]))
            return f"{old}\n... {len(accs) - older - newer} more ...\n{new}"

    def _format_info(self) -> str:
        return (
            f"city: {self.city}"
            f"\nregion: {self.region}"
            f"\ncountry: {self.country}"
            f"\npostal: {self.postal}"
            f"\nloc: {self.loc}"
            f"\ntimezone: {self.timezone}"
            f"\norg: {self.org}"
            f"\nhostname: {self.hostname}"
        )

    def __str__(self) -> str:
        return f"{self.ip}\n{self._format_info()}\n{len(self.accesses)} accesses"

    def __format__(self, format_spec: str) -> str:
        match format_spec:
            case "ip":
                return str(self.ip)
            case "summary":
                return (
                    f"{self.ip}"
                    f"\n\n{self._format_access_times()}"
                    f"\n\n{self._format_info()}"
                )
            case _:
                return super().__format__(format_spec)


class Access(Base):
    __tablename__ = "access"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    host_id = Column(Integer, ForeignKey("ip_info._ip"))
    host = relationship("Info", back_populates="accesses")

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        index=True,
        nullable=False,
    )

    request = Column(String(128), nullable=False)
    status: Mapped[int]

    referrer = Column(String(256))

    user_agent: Mapped[str]
