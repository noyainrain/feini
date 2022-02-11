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
    telegram_key = config.get('telegram', 'key', fallback=None)
    bot = Bot(telegram_key=telegram_key)
    asyncio.run(bot.run())

if __name__ == '__main__':
    main()
