# TODO

"""TODO."""

import asyncio
from asyncio import Task, current_task, get_running_loop
from asyncio import CancelledError
from configparser import ConfigParser
import logging
from typing import cast
import signal
import sys

from .bot import Bot

async def main() -> None:
    loop = get_running_loop()
    task = cast(Task[None], current_task())
    loop.add_signal_handler(signal.SIGINT, task.cancel) # type: ignore[misc]
    loop.add_signal_handler(signal.SIGTERM, task.cancel) # type: ignore[misc]

    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                        level=logging.INFO)
    config = ConfigParser()
    config.read('fe.ini')
    redis_url = config.get('feini', 'redis_url', fallback='redis:')
    try:
        debug = config.getboolean('feini', 'debug', fallback=False)
    except ValueError:
        print('Configuration error: Bad [feini] debug type', file=sys.stderr)
        return
    telegram_key = config.get('telegram', 'key', fallback=None)
    bot = Bot(redis_url=redis_url, debug=debug, telegram_key=telegram_key)
    try:
        await bot.run()
    except CancelledError:
        await bot.close()
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except CancelledError:
        pass
