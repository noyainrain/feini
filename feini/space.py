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

"""TODO.

.. data:: CHARACTER_NAMES

   Name of each character.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Awaitable, Collection, Iterable
from contextlib import asynccontextmanager
import dataclasses
from dataclasses import dataclass, field
from itertools import chain
import random
from random import randint, shuffle
import sys
from typing import Literal, cast, overload, TYPE_CHECKING

from aioredis.exceptions import WatchError

from . import context
from .furniture import Furniture, FURNITURE_TYPES
from .util import Pipeline, Redis, isemoji, randstr

if TYPE_CHECKING:
    from .stories import Story

CHARACTER_NAMES = {
    '👻': 'Ghost'
}

class Space:
    """TODO.

    .. attribute:: time

       Current simulation time.

    .. attribute:: trail_supply

       Current hiking trail resource supply level.

    .. attribute:: pet_nutrition

       Current pet nutrition level.

    .. data:: ITEM_CATEGORIES

       Available types of items by category.

    .. data:: ITEM_WEIGHTS

       Weights by which items are ordered.

    .. data:: COSTS

       TODO.

    .. data:: BLUEPRINT_WEIGHTS

       Weights by which blueprints are ordered.

    .. data:: TRAIL_SUPPLY_FULL

       Level at which a resource is in supply on the trail.
    """

    ITEM_CATEGORIES = {
        'resource': ['🥕', '🪨', '🪵', '🧶'],
        'clothing': ['🧢', '👒', '🎧', '👓', '🕶️', '🥽', '🧣', '🎀', '💍'],
        'tool': ['👋', '✏️', '🧺', '🪓', '✂️', '🔨', '🪡', '🍳', '🧽', '🚿', '🧭']
    }

    ITEM_WEIGHTS = {
        item:
            weight for weight, item
            in enumerate(item for items in ITEM_CATEGORIES.values() for item in items)
    }

    # Material distribution guidelines: 4 - 5 resources for small (S) objects, 6 - 7 for M and 8 - 9
    # for L (for details see ``scripts/material.py``)

    COSTS = {
        # Tools
        '🪓': ['🪨'], # S
        '✂️': ['🪨', '🪨', '🪨', '🪵'], # S
        '🪡': ['🪵', '🪵', '🪵', '🪵', '🪵'], # S
        '🍳': ['🪨', '🪨', '🪨', '🪨', '🪵'], # S
        '🚿': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'], # M
        '🧭': ['🪨', '🪨', '🪨', '🪨'], # S
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

    CLOTHING_MATERIAL = {
        # Head
        '🧢': ['🪵', '🧶', '🧶', '🧶'], # S
        '👒': ['🪵', '🪵', '🪵', '🪵', '🧶'], # S
        '🎧': ['🪨', '🪨', '🧶', '🧶', '🧶'], # S
        # Face
        '👓': ['🪨', '🪨', '🪵', '🪵', '🧶'], # S
        '🕶️': ['🪨', '🪨', '🪵', '🪵', '🧶'], # S
        '🥽': ['🪨', '🪨', '🧶', '🧶', '🧶'], # S
        # Body
        '🧣': ['🧶', '🧶', '🧶', '🧶', '🧶', '🧶'], # M
        '🎀': ['🧶', '🧶', '🧶', '🧶'], # S
        '💍': ['🪨', '🪨', '🪨', '🪨', '🧶'] # S
    }

    BLUEPRINT_WEIGHTS = {blueprint: weight for weight, blueprint in enumerate(COSTS)}

    INTERVAL_S = 7
    MEADOW_VEGETABLE_GROWTH_MAX = 7
    WOODS_GROWTH_MAX = 7
    TRAIL_SUPPLY_FULL = 23
    PET_NUTRITION_MAX = 25
    PET_FUR_MAX = 7

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.chat = data['chat']
        self.time = int(data['time'])
        self.resources = data['resources'].split()
        self.tools = data['tools'].split()
        self.meadow_vegetable_growth = int(data['meadow_vegetable_growth'])
        self.woods_growth = int(data['woods_growth'])
        self.trail_supply = int(data['trail_supply'])
        self.pet_id = data['pet_id']
        self.pet_name = data['pet_name']
        self.pet_is_egg = bool(data['pet_is_egg'])
        self.pet_nutrition = int(data['pet_nutrition'])
        self.pet_fur = int(data['pet_fur'])
        self.pet_activity_id = data['pet_activity_id']

    async def get_pet(self) -> Pet:
        return Pet(await context.bot.get().redis.hgetall(self.pet_id))

    async def get(self) -> Space:
        return await context.bot.get().get_space(self.id)

    async def get_blueprints(self) -> list[str]:
        """Get known blueprints."""
        return await context.bot.get().redis.zrange(f'{self.id}.blueprints', 0, -1)

    async def get_objects(self) -> list[Furniture]:
        bot = context.bot.get()
        key = f'{self.id}.items'
        async with transaction(bot.redis, key) as pipe:
            item_ids = await pipe.lrange(key, 0, -1)
            pipe.multi()
            for item_id in item_ids:
                pipe.hgetall(item_id)
            items = cast(list[dict[str, str]], await pipe.execute())
            return [FURNITURE_TYPES[data['type']](data) for data in items]

    # clean

    async def get_characters(self) -> list[Character]:
        """Get the present characters."""
        redis = context.bot.get().redis
        ids = await redis.lrange(f'{self.id}.characters', 0, -1)
        characters = (await redis.hgetall(character_id) for character_id in ids)
        return [Character(data) # type: ignore[misc]
                async for data in characters if data] # type: ignore[attr-defined,misc]

    async def get_stories(self) -> set[Story]:
        """Get all ongoing stories."""
        def parse_story(data: dict[str, str]) -> Story:
            # pylint: disable=import-outside-toplevel
            from . import stories
            cls = cast('type[Story]', getattr(stories, data['id'].split(':')[0]))
            return cls(data)
        redis = context.bot.get().redis
        ids = await redis.smembers(f'{self.id}.stories')
        stories = (await redis.hgetall(story_id) for story_id in ids)
        return {parse_story(data) # type: ignore[misc]
                async for data in stories if data} # type: ignore[attr-defined,misc]

    # /clean

    async def get_pet_activity(self) -> Object | str:
        if self.pet_activity_id in {'', '💤', '🍃'}:
            return self.pet_activity_id
        return await context.bot.get().get_object(self.pet_activity_id)

    async def tick(self, time: int) -> Space:
        """Simulate the space at *time* for one tick.

        If *time* does not match the current simulation :attr:`time`, the operation is skipped.
        """
        bot = context.bot.get()

        pet = await self.get_pet()
        await pet.tick()
        for item in await self.get_objects():
            await item.tick(time)

        async with bot.redis.pipeline() as pipe:
            furniture_key = f'{self.id}.items'
            await pipe.watch(self.id, furniture_key) # type: ignore[misc]
            space = Space(await pipe.hgetall(self.id))
            furniture_ids = await pipe.lrange(furniture_key, 0, -1)
            #furniture = [await pipe.hget(id, 'type') for id in furniture_ids]

            pipe.multi()
            if space.time == time:
                pet_activity_id = random.choice(['', '💤', '🍃', *furniture_ids])
                pet_nutrition = max(space.pet_nutrition - 1, 0)
                pipe.hset(self.id, mapping={
                    'meadow_vegetable_growth':
                        min(space.meadow_vegetable_growth + 1, self.MEADOW_VEGETABLE_GROWTH_MAX),
                    'woods_growth': min(space.woods_growth + 1, self.WOODS_GROWTH_MAX),
                    'pet_nutrition': pet_nutrition,
                    'pet_fur': min(space.pet_fur + 1, self.PET_FUR_MAX),
                    'pet_activity_id': pet_activity_id
                })
                pipe.hincrby(self.id, 'trail_supply', 1)
                pipe.hincrby(self.id, 'time', 1)
                if pet_nutrition == 0 and space.pet_nutrition == 1:
                    pipe.rpush('events', f'pet-hungry {self.id}')
            pipe.hgetall(self.id)

            data = await cast(Awaitable[list[dict[str, str]]], pipe.execute())
            space = Space(data[-1])

        if pet_activity_id and pet_activity_id not in {'', '💤', '🍃'}:
            obj = await bot.get_object(pet_activity_id)
            await obj.use()

        return space

    # clean

    async def obtain(self, *items: str) -> None:
        """Obtain the given *items*.

        Only available in debug mode.
        """
        bot = context.bot.get()
        if not bot.debug:
            raise ValueError('Disabled bot debug mode')
        for item in items:
            if not any(item in items for items in Space.ITEM_CATEGORIES.values()):
                raise ValueError(f'Unknown items item {item}')

        tools = tuple(item for item in items if item in self.ITEM_CATEGORIES['tool'])
        items = tuple(item for item in items if item not in self.ITEM_CATEGORIES['tool'])
        async with bot.redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'resources', 'tools', 'oink')
            stock = (values[0] or '').split()
            tools_stock = (values[1] or '').split()
            pipe.multi()
            stock = sorted(chain(stock, items), key=Space.ITEM_WEIGHTS.__getitem__)
            tools_stock += tools
            pipe.hset(self.id,
                      mapping={'resources': ' '.join(stock), 'tools': ' '.join(tools_stock)})
            await pipe.execute()

    # /clean

    async def gather_meadow(self) -> list[str]:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split()
            growth = int(await pipe.hget(self.id, 'meadow_vegetable_growth') or '')
            pipe.multi()
            gathered = []
            if growth == self.MEADOW_VEGETABLE_GROWTH_MAX:
                gathered = ['🥕', '🪨']
                resources = sorted(resources + gathered, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id,
                          mapping={'resources': ' '.join(resources), 'meadow_vegetable_growth': 0})
            await pipe.execute()
            return gathered

    async def chop_wood(self) -> list[str]:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            space = Space(await pipe.hgetall(self.id))
            pipe.multi()
            # TODO some abstraction like Tool() / Action()?
            if '🪓' not in space.tools:
                raise ValueError('no axe in tools')
            wood = []
            if space.woods_growth == self.WOODS_GROWTH_MAX:
                wood = ['🪵']
                resources = sorted(space.resources + wood, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'woods_growth': 0})
            await pipe.execute()
            return wood

    @overload
    async def use(self, item: Literal['✂️']) -> list[str]:
        pass
    @overload
    async def use(self, item: str) -> object:
        pass
    async def use(self, item: str) -> object:
        if item == '✂️':
            return await self._shear_pet()
        raise ValueError(f'Invalid item {item}')

    async def _shear_pet(self) -> list[str]:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            space = Space(await pipe.hgetall(self.id))
            if '✂️' not in space.tools:
                raise ValueError('Scissors not in tools')
            pipe.multi()
            wool = []
            if space.pet_fur == self.PET_FUR_MAX:
                wool = ['🧶']
                resources = sorted(space.resources + wool, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'pet_fur': 0})
            await pipe.execute()
            return wool

    # clean

    async def craft(self, blueprint: str) -> str | Furniture:
        """Craft a new object given by *blueprint*."""
        if blueprint in FURNITURE_TYPES:
            return await self._craft_furniture_item(blueprint)
        return await self._craft_tool(blueprint)

    async def _craft_tool(self, blueprint: str) -> str:
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'resources', 'tools')
            items = (values[0] or '').split(' ')
            tools = (values[1] or '').split(' ')
            if await pipe.zscore(f'{self.id}.blueprints', blueprint) is None:
                raise ValueError(f'Unknown blueprint {blueprint}')
            pipe.multi()
            try:
                for resource in self.COSTS[blueprint]:
                    items.remove(resource)
            except ValueError:
                raise ValueError('Missing resources') from None
            tools.append(blueprint)
            pipe.hset(self.id, mapping={'resources': ' '.join(items), 'tools': ' '.join(tools)})
            await pipe.execute()
        return blueprint

    async def _craft_furniture_item(self, blueprint: str) -> Object:
        bot = context.bot.get()
        object_id = f'Object:{randstr()}'

        async with bot.redis.pipeline() as pipe:
            await pipe.watch(self.id)
            items = (await pipe.hget(self.id, 'resources') or '').split(' ')
            if await pipe.zscore(f'{self.id}.blueprints', blueprint) is None:
                raise ValueError(f'Unknown blueprint {blueprint}')
            pipe.multi()
            try:
                for resource in self.COSTS[blueprint]:
                    items.remove(resource)
            except ValueError:
                raise ValueError('Missing resources') from None
            pipe.hset(self.id, 'resources', ' '.join(items))
            pipe.rpush(f'{self.id}.items', object_id)
            await pipe.execute()

        # Note that if there is a crash creating the furniture item, we could create it later from
        # the reserved ID
        return await FURNITURE_TYPES[blueprint].create(object_id, blueprint)

    async def sew(self, pattern: str) -> str:
        """Sew a new clothing item given by *pattern*."""
        try:
            material = self.CLOTHING_MATERIAL[pattern]
        except KeyError:
            raise ValueError(f'Unknown pattern {pattern}') from None

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'resources', 'tools')
            items = (values[0] or '').split()
            tools = (values[1] or '').split()
            pipe.multi()
            if '🪡' not in tools:
                raise ValueError('No tools item 🪡')
            try:
                for item in material:
                    items.remove(item)
            except ValueError:
                raise ValueError('Missing resources') from None
            items.append(pattern)
            items.sort(key=Space.ITEM_WEIGHTS.__getitem__)
            pipe.hset(self.id, 'resources', ' '.join(items))
            await pipe.execute()
        return pattern

    # /clean

    async def touch_pet(self) -> None:
        await context.bot.get().redis.hset(self.id, 'pet_is_egg', '')

    async def feed_pet(self) -> None:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split()
            nutrition = int(await pipe.hget(self.id, 'pet_nutrition') or '')
            pipe.multi()
            if nutrition == self.PET_NUTRITION_MAX:
                raise ValueError('Max pet_nutrition')
            try:
                resources.remove('🥕')
            except ValueError as e:
                raise ValueError('🥕 not in resources') from e
            pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'pet_nutrition': 25})
            await pipe.execute()

    async def change_pet_name(self, name: str) -> Space:
        async with context.bot.get().redis.pipeline() as pipe:
            pipe.hset(self.id, 'pet_name', name)
            pipe.hgetall(self.id)
            data = await cast(Awaitable[list[dict[str, str]]], pipe.execute())
            return Space(data[-1])

    # clean

    async def hike(self) -> Hike:
        """Start a hike.

        A compass 🧭 is required.
        """
        space = Space(await context.bot.get().redis.hgetall(self.id))
        if '🧭' not in space.tools:
            raise ValueError('No tools item 🧭')
        resource = (random.choice(['🥕', '🪨']) if space.trail_supply >= self.TRAIL_SUPPLY_FULL
                    else None)
        return Hike(self, resource=resource)

    async def record_hike(self, hike: Hike) -> None:
        """Record a finished *hike*.

        Any :attr:`Hike.gathered` resources are stored.
        """
        if not hike.finished:
            raise ValueError('Unfinished hike')

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            space = Space(await pipe.hgetall(self.id))
            pipe.multi()
            if '🧭' not in space.tools:
                raise ValueError('No tools item 🧭')
            if hike.gathered:
                if space.trail_supply < self.TRAIL_SUPPLY_FULL:
                    raise ValueError('Empty trail_supply')
                resources = sorted(space.resources + hike.gathered, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'trail_supply': 0})
            await pipe.execute()

    async def tell_stories(self) -> None:
        """Continue all ongoing stories."""
        for story in await self.get_stories():
            try:
                await story.tell()
            except ReferenceError:
                pass

    # /clean

    # TODO later: cook
    # TODO later: website
    # - after crafting furniture, set activity to new object - show std touch msg or something like
    # "feini is very curios"

    # wash_pet() pet_hygiene dirty

class Pet:
    """Pet.

    .. attribute:: clothing

       Clothing the pet is wearing.
    """

    MAX_DIRT = 48 + 1

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.space_id = data['space_id']
        self.dirt = int(data['dirt'])
        self.clothing = data['clothing'] or None

    async def tick(self) -> None:
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            pet = Pet(await pipe.hgetall(self.id))
            pipe.multi()
            pipe.hset(self.id, 'dirt', min(pet.dirt + 1, self.MAX_DIRT))
            if pet.dirt == self.MAX_DIRT - 1:
                pipe.rpush('events', f'pet-dirty {self.space_id}')
            await pipe.execute()

    async def wash(self) -> None:
        """TODO."""
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            dirt = int(await pipe.hget(self.id, 'dirt') or '')
            pipe.multi()
            if not dirt:
                raise ValueError('No dirt')
            pipe.hset(self.id, 'dirt', 0)
            await pipe.execute()

    async def dress(self, clothing: str | None) -> None:
        """Dress the pet in the given *clothing*."""
        if clothing and clothing not in Space.ITEM_CATEGORIES['clothing']:
            raise ValueError(f'Unknown clothing {clothing}')

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id, self.space_id)
            old_clothing = await pipe.hget(self.id, 'clothing') or None
            items = (await pipe.hget(self.space_id, 'resources') or '').split()
            pipe.multi()
            if old_clothing:
                items.append(old_clothing)
                items.sort(key=Space.ITEM_WEIGHTS.__getitem__)
            if clothing:
                try:
                    items.remove(clothing)
                except ValueError:
                    raise ValueError(f'No items item {clothing}') from None
            pipe.hset(self.id, 'clothing', clothing or '')
            pipe.hset(self.space_id, 'resources', ' '.join(items))
            await pipe.execute()

    def __str__(self) -> str:
        return f"🐕{self.clothing or ''}"

# clean

@dataclass
class Message:
    """Dialogue message.

    .. attribute:: id

       Message ID.

    .. attribute:: request

       Items the character currently wants, if any.

    .. attribute:: taken

       Items the player has just given to the character, if any.
    """

    id: str
    request: list[str] = field(default_factory=list)
    taken: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        for item in self.request:
            if not any(item in items
                       for category, items in Space.ITEM_CATEGORIES.items() if category != 'tools'):
                raise ValueError(f'Unknown request item {item}')
        for item in self.taken:
            if not any(item in items
                       for category, items in Space.ITEM_CATEGORIES.items() if category != 'tools'):
                raise ValueError(f'Unknown taken item {item}')

    @staticmethod
    def parse(data: str) -> Message:
        """Parse the string representation *data* into a message."""
        tokens = data.split()
        return Message(tokens[0], tokens[1:])

    def encode(self) -> str:
        """Return a string representation of the message."""
        return ' '.join([self.id, *self.request])

class Character:
    """Non-Player character.

    .. attribute:: id

       Character ID.

    .. attribute:: space_id

       Related :class:`Space` ID.

    .. attribute:: avatar

       Avatar emoji.
    """

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.space_id = data['space_id']
        self.avatar = data['avatar']

    async def get_dialogue(self) -> list[Message]:
        """Get the ongoing dialogue, starting from the most recent message."""
        return [Message.parse(message)
                for message in await context.bot.get().redis.lrange(f'{self.id}.dialogue', 0, -1)]

    async def talk(self) -> Message:
        """Talk to the character and return their reply.

        If the character has requested some items, give the items to them or repeat the request
        message. The final dialogue message is always repeated.
        """
        async with context.bot.get().redis.pipeline() as pipe:
            dialogue_key = f'{self.id}.dialogue'
            await pipe.watch(dialogue_key, self.space_id)
            messages = [Message.parse(message)
                        for message in await pipe.lrange(dialogue_key, 0, 1)]
            message = messages[0]
            next_message = messages[1] if len(messages) > 1 else None
            items = (await pipe.hget(self.space_id, 'resources') or '').split()

            pipe.multi()
            if next_message is None:
                return message
            if message.request:
                try:
                    for item in message.request:
                        items.remove(item)
                    next_message = dataclasses.replace(next_message, taken=message.request)
                except ValueError:
                    return message
            pipe.ltrim(dialogue_key, 1, -1)
            pipe.hset(self.space_id, 'resources', ' '.join(items))
            await pipe.execute()
            return next_message

class Hike:
    """Hike minigame.

    .. attribute:: space

       Related space.

    .. attribute:: map

       Grid of fields.

    .. attribute:: moves

       Moves the player made so far. A move is a list of steps, where each step is a direction
       (➡️⬇️⬅️⬆️.) along with the encountered field.

    .. attribute:: resource

       Resource available on the hike. May be ``None``.

    .. attribute:: gathered

       Resources the player has gathered so far.

    .. data:: RADIUS

       Radius of the map.

    .. data:: GROUND

       Ground fields.

    .. data:: TREES

       Tree fields.
    """

    RADIUS = 4
    GROUND = {'🟩', '✴️'}
    TREES = {'🌲', '🌳'}

    _DISPLACEMENTS = {'➡️': (1, 0), '⬇️': (0, 1), '⬅️': (-1, 0), '⬆️': (0, -1)}
    _DIRECTIONS = {displacement: direction for direction, displacement in _DISPLACEMENTS.items()}

    def __init__(self, space: Space, *, resource: str | None = None) -> None:
        if not (resource is None or resource in Space.ITEM_CATEGORIES['resource']):
            raise ValueError('Bad resource')

        self.space = space
        size = self.RADIUS * 2 + 1
        self.map = [[''] * size for _ in range(size)]
        self.resource = resource
        self.gathered: list[str] = []
        self.moves: list[list[tuple[str, str]]] = []
        self._revealed: set[tuple[int, int]] = set()
        self._generate_map()

    @property
    def finished(self) -> bool:
        """Indicates if the player found the destination."""
        return bool(self.moves and self.moves[-1][-1][1] == '📍')

    def __str__(self) -> str:
        return self.text()

    async def move(self, directions: Collection[str]) -> list[tuple[str, str]]:
        """Move :data:`RADIUS` steps in the given *directions*.

        A description of the move is returned. If the destination is reached, the hike is recorded.
        """
        if len(directions) != self.RADIUS:
            raise ValueError(f"Bad directions length [{', '.join(directions)}]")
        for direction in directions:
            if direction not in self._DISPLACEMENTS:
                raise ValueError(f'Bad directions item {direction}')
        if self.finished:
            raise ValueError('Finished hike')

        move = []
        x, y = self.RADIUS, self.RADIUS
        for direction in directions:
            dx, dy = self._DISPLACEMENTS[direction]
            x, y = x + dx, y + dy
            field = self.map[y][x]
            move.append((direction, field))
            self._revealed.add((x, y))

            if field in self.TREES or field == '📍':
                break
            if field == self.resource:
                self.gathered.append(field)
                self.map[y][x] = '🟩'
        self.moves.append(move)

        if self.finished:
            await self.space.record_hike(self)
        return move

    def find_path(self, field: str) -> list[str]:
        """Find directions to *field*.

        If *field* is not reachable, a :exc:`ValueError` is raised.
        """
        queue = deque([[(self.RADIUS, self.RADIUS)]])
        while queue:
            path = queue.pop()
            x, y = path[-1]
            distance = len(path) - 1

            if distance > self.RADIUS:
                continue
            if path.count((x, y)) > 1:
                continue
            if self.map[y][x] == field:
                return [self._DIRECTIONS[(b[0] - a[0], b[1] - a[1])]
                        for a, b in zip(path, path[1:])]

            for coords in self._get_adjacents(x, y):
                queue.appendleft(path + [coords])
        raise ValueError(f'Unreachable {field}')

    def text(self, *, revealed: bool = False) -> str:
        """Return a text representation of the map.

        Fields not visited by the player so far are hidden, unless *revealed* is set.
        """
        return '\n'.join(
            ''.join(
                field if field and ((x, y) in self._revealed or revealed) else '⬜'
                for x, field in enumerate(row))
            for y, row in enumerate(self.map))

    def _get_adjacents(self, x: int, y: int) -> list[tuple[int, int]]:
        return ([] if self.map[y][x] in self.TREES
                else [(x + dx, y + dy) for dx, dy in self._DISPLACEMENTS.values()])

    def _generate_map(self) -> None:
        # In taxicab geometry (https://en.wikipedia.org/wiki/Taxicab_geometry), a circle is a
        # rotated square with half the area of its circumscribed square
        area = int(len(self.map) ** 2 / 2)
        distances = self._generate_passable(round(area * 2 / 3))
        passable = list(distances.items())
        shuffle(passable)
        def get_distance(field: tuple[tuple[int, int], int]) -> int:
            return field[1]
        passable.sort(key=get_distance)

        # Place trees
        for y, row in enumerate(self.map):
            for x, _ in enumerate(row):
                if abs(self.RADIUS - x) + abs(self.RADIUS - y) <= self.RADIUS:
                    self.map[y][x] = '🌳' if random.random() < 0.25 else '🌲'

        # Place ground
        for coords, _ in passable:
            x, y = coords
            self.map[y][x] = '🟩'

        # Place origin
        x, y = passable.pop(0)[0]
        self.map[y][x] = '✴️'
        self._revealed.add((x, y))

        # Place destination
        x, y = passable.pop()[0]
        self.map[y][x] = '📍'
        self._revealed.add((x, y))

        # Place resource
        if self.resource:
            x, y = random.choice(passable)[0]
            self.map[y][x] = self.resource

    def _generate_passable(self, count: int) -> dict[tuple[int, int], int]:
        distances: dict[tuple[int, int], int] = {}
        bucket = deque([[(self.RADIUS, self.RADIUS)]])
        while bucket:
            path = bucket.pop()
            x, y = path[-1]
            distance = len(path) - 1

            if distance > self.RADIUS:
                continue
            if path.count((x, y)) > 1:
                continue
            if sum(coords in path for coords in self._get_adjacents(x, y)) > 1:
                continue
            if len(distances) >= count and (x, y) not in distances:
                continue
            if distance < distances.get((x, y), sys.maxsize):
                distances[(x, y)] = distance

            for coords in self._get_adjacents(x, y):
                # Note that a flat random bucket is slightly biased towards already visited paths.
                # If needed, this could be improved with a recursive random bucket.
                bucket.insert(randint(0, len(bucket)), path + [coords])
        return distances

# /clean

# TODO kill this, use pipe.watch(...) explicityl, do not retry on watch error,
# just tell the user to try again, it will be so selten, mostly never, really...
@asynccontextmanager
async def transaction(redis: Redis, *watches: str) -> AsyncIterator[Pipeline]:
    async with redis.pipeline() as pipe:
        while True:
            await pipe.watch(*watches) # type: ignore[misc]
            try:
                yield pipe
                break
            except WatchError:
                pass
