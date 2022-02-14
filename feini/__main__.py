# TODO

"""TODO."""

import asyncio
from asyncio import get_event_loop
from configparser import ConfigParser
import logging

from .bot import Bot

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = ConfigParser()
    config.read('feini.ini')
    redis_url = config.get('feini', 'redis_url', fallback='redis:')
    telegram_key = config.get('telegram', 'key', fallback=None)
    bot = Bot(redis_url=redis_url, telegram_key=telegram_key)
    asyncio.run(bot.run())

if __name__ == '__main__':
    main()
