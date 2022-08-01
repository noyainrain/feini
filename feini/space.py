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

"""Logic of pets and their space.

.. data:: CHARACTER_NAMES

   Name of each character.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
import dataclasses
from dataclasses import dataclass, field
from itertools import chain
import random
from random import randint, shuffle
import sys
from typing import cast, TYPE_CHECKING

from . import context
from .core import Entity
from .furniture import Furniture, FURNITURE_TYPES, FURNITURE_MATERIAL
from .util import randstr

if TYPE_CHECKING:
    from .stories import Story

CHARACTER_NAMES = {
    '👻': 'Ghost'
}

class Space(Entity):
    """Space inhabited by a pet.

    .. attribute:: chat

       Chat the space belongs to.

    .. attribute:: time

       Current simulation time.

    .. attribute:: items

       Item inventory.

    .. attribute:: tools

       Tool inventory.

    .. attribute:: meadow_vegetable_growth

       Current vegetable growth level.

    .. attribute:: woods_growth

       Current wood growth level.

    .. attribute:: trail_supply

       Current hiking trail resource supply level.

    .. attribute:: pet_id

       ID of the residing :class:`Pet`.

    .. attribute:: pet_name

       Name of the pet.

    .. attribute:: pet_hatched

       Indicates if the pet has hatched or is still an egg.

    .. attribute:: pet_nutrition

       Current nutrition level of the pet.

    .. attribute:: pet_fur

       Current fur growth level of the pet.

    .. attribute:: pet_activity_id

       Current pet activity emoji or ID of the furniture item the pet is engaged with.

    .. attribute:: MEADOW_VEGETABLE_GROWTH_MAX

       Level at which a vegetable is fully grown.

    .. attribute:: WOODS_GROWTH_MAX

       Level at which wood is fully grown.

    .. attribute:: TRAIL_SUPPLY_MAX

       Level at which a resource is in supply on the trail.

    .. attribute:: ITEM_CATEGORIES

       Available types of items by category.

    .. attribute:: ITEM_WEIGHTS

       Weights by which items are ordered.

    .. attribute:: TOOL_MATERIAL

       Material needed for each tool.

    .. attribute:: CLOTHING_MATERIAL

       Material needed for each clothing item.

    .. attribute:: BLUEPRINT_WEIGHTS

       Weights by which blueprints are ordered.
    """

    MEADOW_VEGETABLE_GROWTH_MAX = 8 - 1
    WOODS_GROWTH_MAX = 8 - 1
    TRAIL_SUPPLY_MAX = 24 - 1

    ITEM_CATEGORIES = {
        'food': ['🥕', '🍲'],
        'resource': ['🪨', '🪵', '🧶'],
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

    TOOL_MATERIAL = {
        '🪓': ['🪨'], # S
        '✂️': ['🪨', '🪨', '🪨', '🪵'], # S
        '🪡': ['🪵', '🪵', '🪵', '🪵', '🪵'], # S
        '🍳': ['🪨', '🪨', '🪨', '🪨', '🪵'], # S
        '🚿': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'], # M
        '🧭': ['🪨', '🪨', '🪨', '🪨'], # S
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

    BLUEPRINT_WEIGHTS = {
        blueprint: weight
        for weight, blueprint in enumerate(chain(TOOL_MATERIAL, FURNITURE_MATERIAL))
    }

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.chat = data['chat']
        self.time = int(data['time'])
        self.items = data['resources'].split()
        self.tools = data['tools'].split()
        self.meadow_vegetable_growth = int(data['meadow_vegetable_growth'])
        self.woods_growth = int(data['woods_growth'])
        self.trail_supply = int(data['trail_supply'])
        self.pet_id = data['pet_id']
        self.pet_name = data['pet_name']
        self.pet_hatched = not bool(data['pet_is_egg'])
        self.pet_nutrition = int(data['pet_nutrition'])
        self.pet_fur = int(data['pet_fur'])
        self.pet_activity_id = data['pet_activity_id']

    async def get_pet(self) -> Pet:
        """Get the residing pet."""
        return await context.bot.get().get_pet(self.pet_id)

    async def get_pet_activity(self) -> Furniture | str:
        """Get the current pet activity emoji or furniture item the pet is engaged with."""
        try:
            return await context.bot.get().get_furniture_item(self.pet_activity_id)
        except ValueError:
            return self.pet_activity_id

    async def get_blueprints(self) -> list[str]:
        """Get known blueprints."""
        return await context.bot.get().redis.zrange(f'{self.id}.blueprints', 0, -1)

    async def get_furniture(self) -> list[Furniture]:
        """Get owned furniture."""
        redis = context.bot.get().redis
        ids = await redis.lrange(f'{self.id}.items', 0, -1)
        return [FURNITURE_TYPES[data['type']](data)
                for item_id in ids if (data := await redis.hgetall(item_id))]

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

    async def tick(self, time: int) -> None:
        """Simulate the space at *time* for one tick.

        If *time* does not match the current simulation :attr:`time`, the operation is skipped.
        """
        pet = await self.get_pet()
        await pet.tick()
        for item in await self.get_furniture():
            await item.tick(time)

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            try:
                sim_time = int(await pipe.hget(self.id, 'time') or '')
            except ValueError:
                raise ReferenceError(self.id) from None
            if time != sim_time:
                return

            pipe.multi()
            pipe.hset(self.id, 'time', sim_time + 1)
            pipe.hincrby(self.id, 'meadow_vegetable_growth', 1)
            pipe.hincrby(self.id, 'woods_growth', 1)
            pipe.hincrby(self.id, 'trail_supply', 1)
            await pipe.execute()

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
            values = await pipe.hmget(self.id, 'resources', 'tools')
            stock = (values[0] or '').split()
            tools_stock = (values[1] or '').split()
            pipe.multi()
            stock = sorted(chain(stock, items), key=Space.ITEM_WEIGHTS.__getitem__)
            tools_stock += tools
            pipe.hset(self.id,
                      mapping={'resources': ' '.join(stock), 'tools': ' '.join(tools_stock)})
            await pipe.execute()

    async def gather(self) -> list[str]:
        """Gather available resources from the meadow and return a receipt."""
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'resources', 'meadow_vegetable_growth')
            if not values:
                raise ReferenceError(self.id)
            items = (values[0] or '').split()
            growth = int(values[1] or '')

            pipe.multi()
            resources = []
            if growth >= self.MEADOW_VEGETABLE_GROWTH_MAX:
                resources = ['🥕', '🪨']
                items = sorted(items + resources, key=self.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id,
                          mapping={'resources': ' '.join(items), 'meadow_vegetable_growth': 0})
            await pipe.execute()
            return resources

    async def chop_wood(self) -> list[str]:
        """Chop available wood from the woods and return a receipt."""
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'resources', 'tools', 'woods_growth')
            if not values:
                raise ReferenceError(self.id)
            items = (values[0] or '').split()
            tools = (values[1] or '').split()
            growth = int(values[2] or '')
            if '🪓' not in tools:
                raise ValueError('No tools item 🪓')

            pipe.multi()
            wood = []
            if growth >= self.WOODS_GROWTH_MAX:
                wood = ['🪵']
                items = sorted(items + wood, key=self.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id, mapping={'resources': ' '.join(items), 'woods_growth': 0})
            await pipe.execute()
            return wood

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
                for resource in self.TOOL_MATERIAL[blueprint]:
                    items.remove(resource)
            except ValueError:
                raise ValueError('Missing items') from None
            tools.append(blueprint)
            pipe.hset(self.id, mapping={'resources': ' '.join(items), 'tools': ' '.join(tools)})
            await pipe.execute()
        return blueprint

    async def _craft_furniture_item(self, blueprint: str) -> Furniture:
        bot = context.bot.get()
        object_id = f'Object:{randstr()}'

        async with bot.redis.pipeline() as pipe:
            await pipe.watch(self.id)
            items = (await pipe.hget(self.id, 'resources') or '').split(' ')
            if await pipe.zscore(f'{self.id}.blueprints', blueprint) is None:
                raise ValueError(f'Unknown blueprint {blueprint}')
            pipe.multi()
            try:
                for resource in FURNITURE_MATERIAL[blueprint]:
                    items.remove(resource)
            except ValueError:
                raise ValueError('Missing items') from None
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
                raise ValueError('Missing items') from None
            items.append(pattern)
            items.sort(key=Space.ITEM_WEIGHTS.__getitem__)
            pipe.hset(self.id, 'resources', ' '.join(items))
            await pipe.execute()
        return pattern

    async def hike(self) -> Hike:
        """Start a hike.

        A compass 🧭 is required.
        """
        space = Space(await context.bot.get().redis.hgetall(self.id))
        if '🧭' not in space.tools:
            raise ValueError('No tools item 🧭')
        resource = (random.choice(['🥕', '🪨']) if space.trail_supply >= self.TRAIL_SUPPLY_MAX
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
                if space.trail_supply < self.TRAIL_SUPPLY_MAX:
                    raise ValueError('Empty trail_supply')
                items = sorted(space.items + hike.gathered, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.id, mapping={'resources': ' '.join(items), 'trail_supply': 0})
            await pipe.execute()

    async def tell_stories(self) -> None:
        """Continue all ongoing stories."""
        for story in await self.get_stories():
            try:
                await story.tell()
            except ReferenceError:
                pass

class Pet(Entity):
    """Pet.

    .. attribute:: space_id

       ID of the :class:`Space` the pet inhabits.

    .. attribute:: dirt

       Current dirtiness level.

    .. attribute:: clothing

       Clothing the pet is wearing.

    .. attribute:: NUTRITION_MAX

       Level at which the pet is full.

    .. attribute:: DIRT_MAX

       Level at which the pet is completely dirty.

    .. attribute:: FUR_MAX

       Level at which the fur is fully grown.
    """

    NUTRITION_MAX = 24 + 1
    DIRT_MAX = 48 + 1
    FUR_MAX = 8 - 1

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.space_id = data['space_id']
        self.dirt = int(data['dirt'])
        self.clothing = data['clothing'] or None

    async def get_space(self) -> Space:
        """Get the space the pet inhabits."""
        return await context.bot.get().get_space(self.space_id)

    async def tick(self) -> None:
        """Simulate the pet for one tick."""
        bot = context.bot.get()
        async with bot.redis.pipeline() as pipe:
            furniture_key = f'{self.space_id}.items'
            await pipe.watch(self.id, self.space_id, furniture_key)
            try:
                nutrition = int(await pipe.hget(self.space_id, 'pet_nutrition') or '')
            except ValueError:
                raise ReferenceError(self.id) from None
            dirt = int(await pipe.hget(self.id, 'dirt') or '')
            furniture_ids = await pipe.lrange(furniture_key, 0, -1)

            pipe.multi()
            nutrition -= 1
            dirt += 1
            activity_id = random.choice(['', '💤', '🍃', *furniture_ids])
            pipe.hset(self.space_id,
                      mapping={'pet_nutrition': nutrition, 'pet_activity_id': activity_id})
            pipe.hset(self.id, 'dirt', dirt)
            pipe.hincrby(self.space_id, 'pet_fur', 1)
            if nutrition == 0:
                pipe.rpush('events', f'pet-hungry {self.space_id}')
            if dirt == self.DIRT_MAX:
                pipe.rpush('events', f'pet-dirty {self.space_id}')
            await pipe.execute()

        try:
            item = await bot.get_furniture_item(activity_id)
        except ValueError:
            pass
        else:
            await item.use()

    async def touch(self) -> None:
        """Touch the pet.

        If the pet is still an egg, it hatches.
        """
        await context.bot.get().redis.hset(self.space_id, 'pet_is_egg', '')

    async def feed(self, food: str) -> None:
        """Feed a vegetable to the pet."""
        if food not in Space.ITEM_CATEGORIES['food']:
            raise ValueError(f'Unknown food {food}')

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.space_id)
            values = await pipe.hmget(self.space_id, 'resources', 'pet_nutrition')
            if not values:
                raise ReferenceError(self.id)
            items = (values[0] or '').split()
            nutrition = int(values[1] or '')
            if nutrition >= self.NUTRITION_MAX:
                raise ValueError('Maximal space pet_nutrition')

            pipe.multi()
            try:
                items.remove(food)
            except ValueError:
                raise ValueError(f'No space items item {food}') from None
            pipe.hset(self.space_id,
                      mapping={'resources': ' '.join(items), 'pet_nutrition': self.NUTRITION_MAX})
            await pipe.execute()

    async def wash(self) -> None:
        """Wash the pet."""
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id)
            try:
                dirt = int(await pipe.hget(self.id, 'dirt') or '')
            except ValueError:
                raise ReferenceError(self.id) from None
            if not dirt:
                raise ValueError('Minimal dirt')
            pipe.multi()
            pipe.hset(self.id, 'dirt', 0)
            await pipe.execute()

    async def dress(self, clothing: str | None) -> None:
        """Dress the pet in the given *clothing*."""
        if clothing and clothing not in Space.ITEM_CATEGORIES['clothing']:
            raise ValueError(f'Unknown clothing {clothing}')

        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id, self.space_id)
            old_clothing = await pipe.hget(self.id, 'clothing')
            if old_clothing is None:
                raise ReferenceError(self.id)
            old_clothing = old_clothing or None
            items = (await pipe.hget(self.space_id, 'resources') or '').split()

            pipe.multi()
            if old_clothing:
                items.append(old_clothing)
                items.sort(key=Space.ITEM_WEIGHTS.__getitem__)
            if clothing:
                try:
                    items.remove(clothing)
                except ValueError:
                    raise ValueError(f'No space items item {clothing}') from None
            pipe.hset(self.id, 'clothing', clothing or '')
            pipe.hset(self.space_id, 'resources', ' '.join(items))
            await pipe.execute()

    async def shear(self) -> list[str]:
        """Shear available wool from the pet and return a receipt."""
        async with context.bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.space_id)
            values = await pipe.hmget(self.space_id, 'resources', 'tools', 'pet_fur')
            if not values:
                raise ReferenceError(self.id)
            items = (values[0] or '').split()
            tools = (values[1] or '').split()
            fur = int(values[2] or '')
            if '✂️' not in tools:
                raise ValueError('No space tools item ✂️')

            pipe.multi()
            wool = []
            if fur >= self.FUR_MAX:
                wool = ['🧶']
                items = sorted(items + wool, key=Space.ITEM_WEIGHTS.__getitem__)
                pipe.hset(self.space_id, mapping={'resources': ' '.join(items), 'pet_fur': 0})
            await pipe.execute()
            return wool

    async def change_name(self, name: str) -> None:
        """Rename the pet to the given *name*."""
        name = name.strip()
        if not name:
            raise ValueError(f'Blank name {name}')
        await context.bot.get().redis.hset(self.space_id, 'pet_name', name)

    def __str__(self) -> str:
        return f"🐕{self.clothing or ''}"

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

       Tile map.

    .. attribute:: moves

       Moves the player made so far. A move is a list of steps, where each step is a direction
       (➡️⬇️⬅️⬆️.) along with the encountered tile.

    .. attribute:: resource

       Resource available on the hike. May be ``None``.

    .. attribute:: gathered

       Resources the player has gathered so far.

    .. data:: RADIUS

       Radius of the map.

    .. data:: GROUND

       Ground tiles.

    .. data:: TREES

       Tree tiles.
    """

    RADIUS = 4
    GROUND = {'🟩', '✴️'}
    TREES = {'🌲', '🌳'}

    _DISPLACEMENTS = {'➡️': (1, 0), '⬇️': (0, 1), '⬅️': (-1, 0), '⬆️': (0, -1)}
    _DIRECTIONS = {displacement: direction for direction, displacement in _DISPLACEMENTS.items()}

    def __init__(self, space: Space, *, resource: str | None = None) -> None:
        if (
            not (resource is None or resource in Space.ITEM_CATEGORIES['resource'] or
                 resource == '🥕')
        ):
            raise ValueError(f'Bad resource {resource}')

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
            tile = self.map[y][x]
            move.append((direction, tile))
            self._revealed.add((x, y))

            if tile in self.TREES or tile == '📍':
                break
            if tile == self.resource:
                self.gathered.append(tile)
                self.map[y][x] = '🟩'
        self.moves.append(move)

        if self.finished:
            await self.space.record_hike(self)
        return move

    def find_path(self, tile: str) -> list[str]:
        """Find directions to *tile*.

        If *tile* is not reachable, a :exc:`ValueError` is raised.
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
            if self.map[y][x] == tile:
                return [self._DIRECTIONS[(b[0] - a[0], b[1] - a[1])]
                        for a, b in zip(path, path[1:])]

            for coords in self._get_adjacents(x, y):
                queue.appendleft(path + [coords])
        raise ValueError(f'Unreachable tile {tile}')

    def text(self, *, revealed: bool = False) -> str:
        """Return a text representation of the map.

        Tiles not visited by the player so far are hidden, unless *revealed* is set.
        """
        return '\n'.join(
            ''.join(
                tile if tile and ((x, y) in self._revealed or revealed) else '⬜'
                for x, tile in enumerate(row))
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
        def get_distance(tile: tuple[tuple[int, int], int]) -> int:
            return tile[1]
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
