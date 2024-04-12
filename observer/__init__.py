import re
from datetime import datetime, timezone
from queue import Queue
from typing import Any

from watchdog.events import FileModifiedEvent, FileSystemEventHandler

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


def _parse_log_line(line: str) -> dict[str, Any]:
    match = _LOG_LINE_PATTERN.match(line)
    if not match:
        # This should never happen under normal circumstances
        raise RuntimeError("Failed to match log line")
    res = match.groupdict()
    res["timestamp"] = datetime.strptime(res["timestamp"], _DATE_FORMAT)
    return res


class ModifiedHandler(FileSystemEventHandler):
    def __init__(
        self,
        queue: Queue,
        last_time: datetime = datetime.now(timezone.utc),
    ):
        self._last_time: datetime = last_time
        self.queue = queue

    def on_modified(self, event: FileModifiedEvent) -> None:
        with open(event.src_path) as f:
            lines = f.readlines()
        new_time = datetime.now(timezone.utc)

        lines = map(_parse_log_line, lines)
        visits: dict[str, list[datetime]] = {}
        for line in lines:
            ip = line["host"]
            visits.setdefault(ip, []).append(line["timestamp"])

        for ip, visit_times in visits.items():
            if max(visit_times) < self._last_time:
                continue

            visit_times.sort()
            self.queue.put((ip, visit_times))

        self._last_time = new_time

    def join(self) -> None:
        self.queue.join()
