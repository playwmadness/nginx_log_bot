import sqlite3

if not sqlite3.threadsafety:
    raise RuntimeError("This build of sqlite3 isn't thread safe")

DB_COLUMNS = {
    "ip": "INT UNSIGNED PRIMARY KEY ASC NOT NULL",
    "hostname": "CHARACTER(256)",
    "org": "CHARACTER(256)",
    "country": "CHARACTER(128)",
    "region": "CHARACTER(128)",
    "city": "CHARACTER(128)",
    "postal": "CHARACTER(32)",
    "loc": "CHARACTER(32)",
    "timezone": "CHARACTER(64)",
}


def _ip_to_int(ip: str) -> int:
    res = 0
    for x in ip.split("."):
        res <<= 8
        res += int(x)
    return res


def _int_to_ip(val: int) -> str:
    return f"{(val >> 24) & 255}.{(val >> 16) & 255}.{(val >> 8) & 255}.{val & 255}"


class Db:
    def __init__(self):
        super().__init__()
        self._connection = sqlite3.connect("db.sqlite3")
        self._cursor = self._connection.cursor()

        self._cursor.execute(
            "CREATE TABLE IF NOT EXISTS ipinfo("
            + ", ".join(map(" ".join, DB_COLUMNS.items()))
            + ")"
        )

    def find_ip(self, ip: str) -> dict | None:
        entry = self._cursor.execute(
            f"SELECT * FROM ipinfo WHERE ip={_ip_to_int(ip)}"
        ).fetchone()
        if not entry:
            return None
        res = {}
        res.update(zip(DB_COLUMNS.keys(), entry))
        res["ip"] = ip
        return res

    def save_ipinfo(self, info: dict) -> None:
        values = (
            _ip_to_int(info["ip"]),
            *[info.get(k, "") for k in DB_COLUMNS.keys()][1:],
        )
        self._cursor.execute(f"INSERT INTO ipinfo VALUES {values}")
        self._connection.commit()
