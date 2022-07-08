# Open Feini
# Copyright (C) 2022 Open Feini contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU
# Affero General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>.

"""Open Feini script."""

import asyncio
from asyncio import CancelledError, Task, current_task, get_running_loop
from configparser import ConfigParser
import logging
import signal
import sys
from typing import cast

from .bot import Bot

async def main() -> None:
    """Run Open Feini."""
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
    try:
        bot = Bot(redis_url=redis_url, telegram_key=telegram_key, debug=debug)
    except ValueError:
        print(f'Configuration error: Bad [feini] redis_url {redis_url}', file=sys.stderr)
        return

    try:
        await bot.run()
    except CancelledError:
        await bot.close()
        raise

try:
    asyncio.run(main())
except CancelledError:
    pass
