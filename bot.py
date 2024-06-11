#!/usr/bin/env python3

import os
import sys
from enum import IntEnum
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from time import sleep
from typing import Any, Union

from dotenv import load_dotenv
from sqlalchemy import create_engine
from watchdog.events import FileModifiedEvent
from watchdog.observers import Observer

from ipinfo import db_models
from observer import ModifiedHandler
from tg import BotThread


class ExitCode(IntEnum):
    OK = 0
    NO_FILEPATH = 1
    NO_FILE = 2
    NO_ENVVARS = 3
    FAILED_TO_START_BOT = 7
    OTHER = 127


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

    def _shutdown(self, *_) -> None:
        self._is_shutdown = True

    @property
    def shutdown(self) -> bool:
        return self._is_shutdown


def main(argv: list[str]) -> ExitCode:
    if not argv:
        print("Expected file path argument", file=sys.stderr)
        return ExitCode.NO_FILEPATH

    if not Path(argv[0]).is_file():
        print(f"Expected {argv[0]} to be a regular file", file=sys.stderr)
        return ExitCode.NO_FILE

    load_dotenv()
    _envvars = [
        "IPINFO_API_KEY",
        "TELEGRAM_API_KEY",
        "TELEGRAM_USER_ID",
        "ENGINE_URL",
    ]
    envvars: dict[str, Any] = {key: os.getenv(key) for key in _envvars}

    if fails := tuple(filter(lambda x: x[1] is None, envvars.items())):
        print("Not all env vars were found:", file=sys.stderr)
        for f, _ in fails:
            print(f, file=sys.stderr)
        return ExitCode.NO_ENVVARS

    s = Shutdown()

    db_engine = create_engine(envvars["ENGINE_URL"])
    db_models.Base.metadata.create_all(db_engine)

    bot = BotThread(
        envvars["IPINFO_API_KEY"],
        db_engine,
        envvars["TELEGRAM_API_KEY"],
        envvars["TELEGRAM_USER_ID"],
    )

    try:
        bot.start()
    except RuntimeError:
        print("Failed to start Telegram Bot Thread", file=sys.stderr)
        return ExitCode.FAILED_TO_START_BOT

    handler = ModifiedHandler(bot.queue, bot.last_access())

    observer = Observer()
    observer.schedule(handler, argv[0], event_filter=(FileModifiedEvent,))

    exit_status: ExitCode = ExitCode.OK
    print("Starting...")

    handler.on_modified(FileModifiedEvent(argv[0], is_synthetic=True))
    observer.start()

    try:
        while not s.shutdown:
            sleep(1)
    except Exception as e:
        exit_status = ExitCode.OTHER
        print(e, file=sys.stderr)
    finally:
        print("Shutting down...")
        observer.stop()
        observer.join()
        bot.stop()
        bot.join()

    return exit_status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
