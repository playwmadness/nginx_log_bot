import asyncio
from datetime import datetime
from queue import Empty, Queue
from threading import Thread

from telegram import Bot as TelegramBot
from telegram.constants import ParseMode

from ipinfo import IpInfo


class BotThread(Thread):
    def __init__(
        self,
        ipinfo_api_key: str,
        tg_api_key: str,
        chat_id: str,
        queue_size: int = 32,
    ):
        super().__init__()
        self.queue = Queue(queue_size)
        self._ipinfo_api_key = ipinfo_api_key
        self._tg_api_key = tg_api_key
        self._chat_id = chat_id
        self._running = False

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._run())

    async def _run(self) -> None:
        async with IpInfo(self._ipinfo_api_key) as ipinfo:
            async with TelegramBot(self._tg_api_key) as bot:
                self._running = True
                while self._running or not self.queue.empty():
                    try:
                        (ip, visits) = self.queue.get(timeout=1)
                    except Empty:
                        continue
                    info = await ipinfo.find_ip(ip)
                    await bot.send_message(  # pyright: ignore
                        chat_id=self._chat_id,
                        text=self._compose_message(info, visits),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )
                    self.queue.task_done()

    def _compose_message(
        self,
        info: dict[str, str],
        visits_list: list[datetime],
    ) -> str:
        if len(visits_list) <= 4:
            visits = "\n".join(map(str, visits_list))
        else:
            visits = "\n".join(
                (
                    str(visits_list[0]),
                    f"... {len(visits_list) - 3} more ...",
                    str(visits_list[-2]),
                    str(visits_list[-1]),
                )
            )

        info_str = "\n".join(f"{k}: {v}" for k, v in info.items())
        return f"```\n{info['ip']}\n\n{visits}\n\n{info_str}\n```"

    def join(self) -> None:
        super().join()
        self.queue.join()

    def stop(self) -> None:
        self._running = False
