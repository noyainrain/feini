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

# pylint: disable=missing-docstring

from asyncio import Task, all_tasks
from collections.abc import AsyncIterator
from configparser import ConfigParser
from contextlib import asynccontextmanager
from typing import cast

from feini.furniture import TMDB
from .test_bot import TestCase

@asynccontextmanager
async def wait_for_background_task() -> AsyncIterator[None]:
    tasks = cast(set[Task[None]], all_tasks())
    yield
    try:
        await (cast(set[Task[None]], all_tasks()) - tasks).pop()
    except KeyError:
        pass

class TMDBTest(TestCase):
    async def test_get_shows(self) -> None:
        config = ConfigParser()
        config.read('fe.ini')
        key = config.get('tmdb', 'key', fallback='') or None
        if not key:
            self.skipTest('Missing [tmdb] key')
        tmdb = TMDB(key=key)

        async with wait_for_background_task():
            # pylint: disable=pointless-statement
            tmdb.shows
        self.assertGreater(len(tmdb.shows), 1)
        self.assertRegex(tmdb.shows[0].url, r'^https://www.themoviedb.org/tv/.+')

class DWTest(TestCase):
    async def test_get_articles(self) -> None:
        async with wait_for_background_task():
            # pylint: disable=pointless-statement
            self.bot.dw.articles
        self.assertGreater(len(self.bot.dw.articles), 1)
        self.assertRegex(self.bot.dw.articles[0].url, '^https://www.dw.com/en/')
