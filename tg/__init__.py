import asyncio
from datetime import datetime
from queue import Empty, Queue
from threading import Semaphore, Thread

from sqlalchemy import Engine
from telegram import Bot as TelegramBot
from telegram.constants import ParseMode

from ipinfo import IpInfo
from ipinfo.db_models import Access


class BotThread(Thread):
    def __init__(
        self,
        ipinfo_api_key: str,
        db_engine: Engine,
        tg_api_key: str,
        chat_id: str,
        queue_size: int = 32,
    ):
        super().__init__()
        self._queue: Queue[tuple[str, list[Access]]] = Queue(queue_size)
        self._ipinfo_api_key = ipinfo_api_key
        self._db_engine = db_engine
        self._tg_api_key = tg_api_key
        self._chat_id = chat_id

        self._running = False
        self._startup = Semaphore(0)

        self._ipinfo = None
        self._tg_bot = None

    @property
    def queue(self) -> Queue[tuple[str, list[Access]]]:
        r"""
        Consumer queue for log entries
        """
        return self._queue

    def start(self, init_timeout: float = 1) -> None:
        super().start()
        if not self._startup.acquire(timeout=init_timeout):
            raise RuntimeError("Failed to initialize BotThread")

    def last_access(self) -> datetime:
        r"""
        :return: The most recent log entry timestamp present in the database.
        """
        try:
            return self._ipinfo.last_access()  # pyright: ignore
        except AttributeError as e:
            raise RuntimeError("BotThread isn't running", e)

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._run())

    async def _run(self) -> None:
        try:
            async with IpInfo(self._ipinfo_api_key, self._db_engine) as self._ipinfo:
                async with TelegramBot(self._tg_api_key) as self._tg_bot:
                    self._running = True
                    self._startup.release()
                    while self._running or not self._queue.empty():
                        try:
                            (ip, visits) = self._queue.get(timeout=1)
                        except Empty:
                            continue
                        info = await self._ipinfo.find_and_update(ip, visits)
                        await self._tg_bot.send_message(
                            chat_id=self._chat_id,
                            text=f"```\n{info:summary}\n```",
                            parse_mode=ParseMode.MARKDOWN_V2,
                        )
                        self._queue.task_done()
        finally:
            self._tg_bot = None
            self._ipinfo = None

    def join(self) -> None:
        super().join()
        self._queue.join()

    def stop(self) -> None:
        r"""
        Stops the bot thread.
        """
        self._running = False
