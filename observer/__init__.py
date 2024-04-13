import re
from datetime import datetime, timezone
from queue import Queue

from watchdog.events import FileModifiedEvent, FileSystemEventHandler

from ipinfo.db_models import Access

_DATE_FORMAT = "%d/%b/%Y:%H:%M:%S %z"
_LOG_LINE_PATTERN = re.compile(
    r"\s*"
    r"(?P<host>\S+)\s+"
    r"(?P<ident>\S+)\s+"
    r"(?P<user>\S+)\s+"
    r"\[(?P<timestamp>.+?)\]\s+"
    r"\"(?P<request>.+?)\"\s+"
    r"(?P<status>\S+)\s+"
    r"(?P<size>\S+)\s+"
    r"\"(?P<referrer>.+?)\"\s+"
    r"\"(?P<user_agent>.+?)\"\s*"
)


def _parse_log_line(line: str) -> tuple[str, Access]:
    match = _LOG_LINE_PATTERN.match(line)
    if not match:
        # This should never happen with the default nginx logger
        raise RuntimeError("Failed to match log line")
    res = match.groupdict()
    res["timestamp"] = (
        datetime.strptime(res["timestamp"], _DATE_FORMAT)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    res = {k: v for k, v in res.items() if v and v != "-"}
    ip = res.pop("host")
    return (
        ip,
        Access(
            timestamp=res["timestamp"],
            request=res.get("request", ""),
            status=res["status"],
            referrer=res.get("referrer"),
            user_agent=res.get("user_agent", ""),
        ),
    )


class ModifiedHandler(FileSystemEventHandler):
    def __init__(
        self,
        queue: Queue[tuple[str, list[Access]]],
        last_time: datetime,
    ):
        self._last_time: datetime = last_time
        self._queue = queue

    def on_modified(self, event: FileModifiedEvent) -> None:
        with open(event.src_path) as f:
            lines = f.readlines()
        new_time = self._last_time

        accesses: dict[str, list[Access]] = {}
        for ip, access in map(_parse_log_line, lines):
            if access.timestamp <= self._last_time:
                continue
            new_time = max(new_time, access.timestamp)
            accesses.setdefault(ip, []).append(access)

        for item in accesses.items():
            self._queue.put(item)

        self._last_time = new_time
