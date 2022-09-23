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

"""Available furniture.

.. data:: FURNITURE_MATERIAL

   Material needed for each furniture item.

.. data:: FURNITURE_TYPES

   Furniture classes.
"""

from __future__ import annotations

import asyncio
from asyncio import Task, create_task
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from logging import getLogger
from functools import partial
import json
from json import JSONDecodeError
import random
from typing import cast
from xml.sax import SAXParseException

from aiohttp import ClientError
import feedparser
from feedparser import ThingsNobodyCaresAboutButMe

from . import context
from .core import Entity
from .util import JSONObject, cancel, raise_for_status

FURNITURE_MATERIAL = {
    # Toys
    '🪃': ['🪵', '🪵'], # S
    '⚾': ['🪵', '🪵', '🧶', '🧶', '🧶'], # S
    '🧸': ['🪨', '🧶', '🧶', '🧶', '🧶'], # S
    # Furniture
    '🛋️': ['🪨', '🪵', '🪵', '🪵', '🪵', '🧶', '🧶', '🧶', '🧶'], # L
    '🪴': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵', '🪵'], # M
    '⛲': ['🪨', '🪨', '🪨', '🪨', '🪨', '🪨', '🪨', '🪨'], # L
    # Devices
    '📺': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'], # M
    # Miscellaneous
    '🗞️': ['🪵', '🪵', '🪵',  '🧶'], # S
    '🎨': ['🪵', '🪵', '🪵', '🪵', '🪨', '🧶', '🧶'] # M
}

class Furniture(Entity):
    """Piece of furniture.

    .. attribute:: type

       Type of furniture as emoji.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.type = data['type']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Furniture:
        """Create a furniture item of the given *furniture_type* with *furniture_id*."""
        data = {'id': furniture_id, 'type': furniture_type}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Furniture(data)

    async def tick(self, time: int) -> None:
        """Simulate the furniture piece at *time* for one tick."""

    async def use(self) -> None:
        """Use the furniture piece."""

    def __str__(self) -> str:
        return self.type

class Houseplant(Furniture):
    """Houseplant.

    .. attribute:: state

       Current state emoji.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Houseplant:
        data = {'id': furniture_id, 'type': '🪴', 'state': '🪴'}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Houseplant(data)

    async def tick(self, time: int) -> None:
        if (time + 1) % 24 == 0:
            await context.bot.get().redis.hset(self.id, 'state', random.choice(['🪴', '🌺']))

    def __str__(self) -> str:
        return self.state

class Television(Furniture):
    """Television set.

    .. attribute:: show

       Current TV show.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.show = Content.parse(data['show'])

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Television:
        bot = context.bot.get()
        data = {'id': furniture_id, 'type': '📺', 'show': str(random.choice(bot.tmdb.shows))}
        await bot.redis.hset(furniture_id, mapping=data)
        return Television(data)

    async def use(self) -> None:
        bot = context.bot.get()
        await bot.redis.hset(self.id, 'show', str(random.choice(bot.tmdb.shows)))

class Newspaper(Furniture):
    """Newspaper.

    .. attribute:: article

       Opened news article.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.article = Content.parse(data['article'])

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Newspaper:
        bot = context.bot.get()
        data = {'id': furniture_id, 'type': '🗞️', 'article': str(random.choice(bot.dw.articles))}
        await bot.redis.hset(furniture_id, mapping=data)
        return Newspaper(data)

    async def use(self) -> None:
        bot = context.bot.get()
        await bot.redis.hset(self.id, 'article', str(random.choice(bot.dw.articles)))

class Palette(Furniture):
    """Canvas and palette.

    .. attribute:: state

       Current state emoji.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Palette:
        data = {'id': furniture_id, 'type': '🎨', 'state': '🎨'}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Palette(data)

    async def tick(self, time: int) -> None:
        if (time + 1) % 24 == 0:
            await context.bot.get().redis.hset(self.id, 'state', random.choice(['🎨', '🖼️']))

    def __str__(self) -> str:
        return self.state

@dataclass
class Content:
    """Media content.

    .. attribute:: title

       Title of the content.
    """

    title: str

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Blank title')

    @staticmethod
    def parse(data: str) -> Content:
        """Parse the string representation *data* into media content."""
        return Content(data)

    def __str__(self) -> str:
        return self.title

class TMDB:
    """The Movie Database source.

    .. attribute:: CACHE_TTL

       Time to live for cached content.

    .. attribute:: key

       TMDB API v4 key to fetch the current popular TV shows.
    """

    CACHE_TTL = timedelta(days=1)

    def __init__(self, *, key: str | None = None) -> None:
        self.key = key
        self._shows = [Content('Buffy the Vampire Slayer')]
        self._cache_expires = datetime.now()
        self._fetch_task: Task[None] | None = None

    @property
    def shows(self) -> list[Content]:
        """Current TV shows, ordered by popularity, highest first."""
        if (
            datetime.now() >= self._cache_expires and
            (not self._fetch_task or self._fetch_task.done())
        ):
            self._fetch_task = create_task(self._fetch())
        return self._shows

    async def _fetch(self) -> None:
        if not self.key:
            return

        logger = getLogger(__name__)
        try:
            headers = {'Authorization': f'Bearer {self.key}'}
            response = await context.bot.get().http.get('https://api.themoviedb.org/3/tv/popular',
                                                        headers=headers)
            await raise_for_status(response)
            loads = partial(cast(Callable[[], object], json.loads), object_hook=JSONObject)
            result = await cast(Awaitable[object], response.json(loads=loads))

            if not isinstance(result, JSONObject):
                raise TypeError(f'Bad result type {type(result).__name__}')
            shows = result.get('results', cls=list)
            if not shows:
                raise ValueError('No results')
            def parse_show(data: object) -> Content:
                if not isinstance(data, JSONObject):
                    raise TypeError(f'Bad show type {type(data).__name__}')
                return Content(title=data.get('name', cls=str))
            self._shows = [parse_show(data) for data in shows[:10]]
            self._cache_expires = datetime.now() + self.CACHE_TTL
            logger.info('Fetched %d show(s) from TMDB', len(self._shows))

        # Work around spurious Any for as target (see https://github.com/python/mypy/issues/13167)
        except (ClientError, asyncio.TimeoutError, JSONDecodeError, TypeError, # type: ignore[misc]
                ValueError) as e:
            if isinstance(e, asyncio.TimeoutError):
                e = asyncio.TimeoutError('Stalled request')
            logger.error('Failed to fetch shows from TMDB (%s)', e)

    async def close(self) -> None:
        """Close the source."""
        if self._fetch_task:
            await cancel(self._fetch_task)

class DW:
    """Deutsche Welle source.

    .. attribute:: CACHE_TTL

       Time to live for cached content.
    """

    CACHE_TTL = timedelta(days=1)

    def __init__(self) -> None:
        self._articles = [Content('Digital pet Tamagotchi turns 25')]
        self._cache_expires = datetime.now()
        self._fetch_task: Task[None] | None = None

    @property
    def articles(self) -> list[Content]:
        """Current news articles, ordered by time, latest first."""
        if (
            datetime.now() >= self._cache_expires and
            (not self._fetch_task or self._fetch_task.done())
        ):
            self._fetch_task = create_task(self._fetch())
        return self._articles

    async def _fetch(self) -> None:
        logger = getLogger(__name__)
        try:
            response = await context.bot.get().http.get('https://rss.dw.com/atom/rss-en-top')
            await raise_for_status(response)
            data = await response.read()

            feed = feedparser.parse(data, sanitize_html=False)
            if feed['bozo']:
                raise cast(Exception, feed['bozo_exception'])
            entries = cast(list[dict[str, str]], feed['entries'])
            if not entries:
                raise ValueError('No entries')
            self._articles = [Content(entry.get('title', '')) for entry in entries]
            self._cache_expires = datetime.now() + self.CACHE_TTL
            logger.info('Fetched %d article(s) from DW', len(self._articles))

        # Work around spurious Any for as target (see https://github.com/python/mypy/issues/13167)
        except (ClientError, asyncio.TimeoutError, ThingsNobodyCaresAboutButMe, # type: ignore[misc]
                SAXParseException, ValueError) as e:
            if isinstance(e, asyncio.TimeoutError):
                e = asyncio.TimeoutError('Stalled request')
            logger.error('Failed to fetch articles from DW (%s)', e)

    async def close(self) -> None:
        """Close the source."""
        if self._fetch_task:
            await cancel(self._fetch_task)

FURNITURE_TYPES = {
    # Toys
    '🪃': Furniture,
    '⚾': Furniture,
    '🧸': Furniture,
    # Furniture
    '🛋️': Furniture,
    '🪴': Houseplant,
    '⛲': Furniture,
    # Devices
    '📺': Television,
    # Miscellaneous
    '🗞️': Newspaper,
    '🎨': Palette
}
