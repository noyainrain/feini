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

.. data:: FURNITURE_TYPES

   Furniture classes.
"""

from __future__ import annotations

import random
from typing import TypeVar

from . import context

_S = TypeVar('_S', bound='Furniture')

class Furniture:
    """Piece of furniture.

    .. attribute:: id

       Furniture item ID.

    .. attribute:: type

       Type of furniture as emoji.
    """

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.type = data['type']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Furniture:
        """Create a furniture item of the given *furniture_type* with *furniture_id*."""
        data = {'id': furniture_id, 'type': furniture_type}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Furniture(data)

    async def get(self: _S) -> _S:
        """Get a fresh copy of the furniture item."""
        data = await context.bot.get().redis.hgetall(self.id)
        if not data:
            raise ReferenceError(self.id)
        return type(self)(data)

    async def tick(self, time: int) -> None:
        """Simulate the furniture piece at *time* for one tick."""

    async def use(self) -> None:
        """Use the furniture piece."""

    def __str__(self) -> str:
        return self.type

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Furniture) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

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

       Current show.
    """

    # Retrieved from https://www.rottentomatoes.com/browse/tv-list-2 on Feb 14 2022
    _SHOWS = [
        'The Book of Boba Fett',
        'Reacher',
        'Euphoria',
        'The Woman In The House Across The Street From The Girl In The Window',
        'All of Us Are Dead',
        'Raised by Wolves',
        'Peacemaker',
        'Pam & Tommy',
        'Inventing Anna',
        'The Sinner'
    ]

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.show = data['show']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Television:
        data = {'id': furniture_id, 'type': '📺', 'show': random.choice(Television._SHOWS)}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Television(data)

    async def use(self) -> None:
        await context.bot.get().redis.hset(self.id, 'show', random.choice(self._SHOWS))

class Newspaper(Furniture):
    """Newspaper.

    .. attribute:: article

       Opened article.
    """

    # Retrieved from https://rss.nytimes.com/services/xml/rss/nyt/world.xml on Feb 14 2022
    _ARTICLES = [
        ('Canada Live Updates: Crossings at Blockaded Canadian Bridge May Resume Soon as Police '
         'Move In'),
        'The Quiet Flight of Muslims From France',
        'Swiss Approve Ban on Tobacco Ads',
        'In Hawaii, Blinken Aims for a United Front With Allies on North Korea',
        ('Ukraine Live Updates: Airlines Suspend Flights as German Leader Warns of ‘Serious Threat '
         'to Peace’'),
        'Finland’s President Knows Putin Well. And He Fears for Ukraine.',
        'Biden’s Decision on Frozen Funds Stokes Anger Among Afghans',
        'Black Authors Shake Up Brazil’s Literary Scene',
        'In Ottawa Trucker Protests, a Pressing Question: Where Were the Police?',
        'Emmanuel Macron Recounts Face-Off With Vladimir Putin'
    ]

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.article = data['article']

    @staticmethod
    async def create(furniture_id: str, furniture_type: str) -> Newspaper:
        data = {'id': furniture_id, 'type': '🗞️', 'article': random.choice(Newspaper._ARTICLES)}
        await context.bot.get().redis.hset(furniture_id, mapping=data)
        return Newspaper(data)

    async def use(self) -> None:
        await context.bot.get().redis.hset(self.id, 'article', random.choice(self._ARTICLES))

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
