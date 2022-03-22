# TODO

"""TODO."""

import asyncio
from asyncio import CancelledError
from configparser import ConfigParser
import logging
import sys

from .bot import Bot

async def main() -> None:
    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                        level=logging.INFO)
    config = ConfigParser()
    config.read('feini.ini')
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
    except KeyboardInterrupt:
        pass
