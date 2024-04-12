#!/usr/bin/env python3

import asyncio
import os
import sys
from asyncio.exceptions import CancelledError
from datetime import datetime, timezone
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from typing import Union

from dotenv import load_dotenv
from watchdog.events import FileModifiedEvent
from watchdog.observers import Observer

from observer import ModifiedHandler
from tg import BotThread


class Shutdown:
    _instance: Union["Shutdown", None] = None

    def __new__(cls):
        if not Shutdown._instance:
            Shutdown._instance = super(Shutdown, cls).__new__(cls)
            signal(SIGTERM, Shutdown._instance._shutdown)
            signal(SIGINT, Shutdown._instance._shutdown)
        return Shutdown._instance

    def __init__(self):
        self._is_shutdown = False

    def _shutdown(self, signum, frame):
        self._is_shutdown = True

    @property
    def shutdown(self):
        return self._is_shutdown


async def main(argv: list[str]) -> int:
    if not argv:
        print("Expected file path argument", file=sys.stderr)
        return 1

    if not Path(argv[0]).is_file():
        print(f"Expected {argv[0]} to be a regular file")
        return 2

    load_dotenv()
    keys = [
        "IPINFO_API_KEY",
        "TELEGRAM_API_KEY",
        "TELEGRAM_USER_ID",
    ]
    keys = {key: os.getenv(key) for key in keys}

    if fails := tuple(filter(lambda x: x[1] is None, keys.items())):
        print("Not all env vars were found:", file=sys.stderr)
        for f, _ in fails:
            print(f, file=sys.stderr)
        return 3

    bot = BotThread(
        keys["IPINFO_API_KEY"],  # pyright: ignore
        keys["TELEGRAM_API_KEY"],  # pyright: ignore
        keys["TELEGRAM_USER_ID"],  # pyright: ignore
    )

    handler = ModifiedHandler(bot.queue)

    observer = Observer()
    observer.schedule(handler, argv[0], event_filter=(FileModifiedEvent,))

    exit_status: int = 0
    try:
        s = Shutdown()
        if not s.shutdown:
            bot.start()
            observer.start()
        print("Running...")
        while not s.shutdown:
            await asyncio.sleep(1)
    except CancelledError as e:
        pass
    except Exception as e:
        exit_status = 127
        print(e, file=sys.stderr)
    finally:
        print("Shutting down...")
        observer.stop()
        observer.join()
        bot.stop()
        bot.join()

    return exit_status


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
