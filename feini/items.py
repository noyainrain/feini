"""TODO."""

from __future__ import annotations

import random

from . import context

class Object:
    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.type = data['type']

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Object) and self.id == other.id

    @staticmethod
    async def create(id: str, typ: str) -> Object:
        data = {'id': id, 'type': typ}
        await context.bot.get().redis.hset(id, mapping=data)
        return Object(data)

    async def tick(self, time: int) -> None:
        pass

    async def use(self) -> None:
        pass

class Plant(Object):
    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(id: str, typ: str = '') -> Plant:
        data = {'id': id, 'type': '🪴', 'state': '🪴'}
        await context.bot.get().redis.hset(id, mapping=data)
        return Plant(data)

    async def tick(self, time: int) -> None:
        if time % 24 == 0:
            await context.bot.get().redis.hset(self.id, 'state', random.choice(['🪴', '🌺']))

class Television(Object):
    # https://www.rottentomatoes.com/browse/tv-list-2
    SHOWS = [
        'The Book of Boba Fett', 'Reacher', 'Euphoria',
        'The Woman In The House Across The Street From The Girl In The Window',
        'All of Us Are Dead', 'Raised by Wolves', 'Peacemaker', 'Pam & Tommy', 'Inventing Anna',
        'The Sinner'
    ]

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.show = data['show']

    @staticmethod
    async def create(id: str, typ: str = '') -> Television:
        data = {'id': id, 'type': '📺', 'show': random.choice(Television.SHOWS)}
        await context.bot.get().redis.hset(id, mapping=data)
        return Television(data)

    async def use(self) -> None:
        await context.bot.get().redis.hset(self.id, 'show', random.choice(self.SHOWS))

class Newspaper(Object):
    ARTICLES = [
        'Canada Live Updates: Crossings at Blockaded Canadian Bridge May Resume Soon as Police Move In',
        'The Quiet Flight of Muslims From France',
        'Swiss Approve Ban on Tobacco Ads',
        'In Hawaii, Blinken Aims for a United Front With Allies on North Korea',
        'Ukraine Live Updates: Airlines Suspend Flights as German Leader Warns of ‘Serious Threat to Peace’',
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
    async def create(id: str, typ: str = '') -> Newspaper:
        data = {'id': id, 'type': '🗞️', 'article': random.choice(Newspaper.ARTICLES)}
        await context.bot.get().redis.hset(id, mapping=data)
        return Newspaper(data)

    async def use(self) -> None:
        await context.bot.get().redis.hset(self.id, 'article', random.choice(self.ARTICLES))

class Palette(Object):
    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(id: str, typ: str) -> Palette:
        data = {'id': id, 'type': '🎨', 'state': '🎨'}
        await context.bot.get().redis.hset(id, mapping=data)
        return Palette(data)

    async def tick(self, time: int) -> None:
        if time % 24 == 0:
            await context.bot.get().redis.hset(self.id, 'state', random.choice(['🎨', '🖼️']))
