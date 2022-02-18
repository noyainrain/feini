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

"""TODO."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
import random
from typing import Literal, cast, overload

from aioredis.exceptions import WatchError

from . import context
from .items import Object
from .util import Pipeline, Redis, randstr

class Space:
    INTERVAL_S = 7
    MEADOW_VEGETABLE_GROWTH_MAX = 7
    WOODS_GROWTH_MAX = 7
    PET_NUTRITION_MAX = 25
    PET_FUR_MAX = 7

    @staticmethod
    def _resource_order(resource: str) -> int:
        return {'🥕': 0, '🪨': 1, '🪵': 2, '🧶': 3}[resource]

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.chat = data['chat']
        self.time = int(data['time'])
        self.resources = data['resources'].split()
        self.tools = data['tools'].split()
        self.meadow_vegetable_growth = int(data['meadow_vegetable_growth'])
        self.woods_growth = int(data['woods_growth'])
        self.pet_id = data['pet_id']
        self.pet_name = data['pet_name']
        self.pet_is_egg = bool(data['pet_is_egg'])
        self.pet_nutrition = int(data['pet_nutrition'])
        self.pet_fur = int(data['pet_fur'])
        self.pet_activity_id = data['pet_activity_id']
        self.story = data['story']

    async def get_pet(self) -> Pet:
        return Pet(await context.bot.get().redis.hgetall(self.pet_id))

    async def get(self) -> Space:
        return await context.bot.get().get_space(self.id)

    async def get_objects(self) -> list[Object]:
        bot = context.bot.get()
        key = f'{self.id}.items'
        async with transaction(bot.redis, key) as pipe:
            item_ids = await pipe.lrange(key, 0, -1)
            pipe.multi()
            for item_id in item_ids:
                pipe.hgetall(item_id)
            items = cast(list[dict[str, str]], await pipe.execute())
            return [bot.object_types[data['type']](data) for data in items]

    async def get_pet_activity(self) -> Object | str:
        if self.pet_activity_id in {'', '💤', '🍃'}:
            return self.pet_activity_id
        return await context.bot.get().get_object(self.pet_activity_id)

    async def tick(self, time: int) -> Space:
        bot = context.bot.get()

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
                if pet_nutrition == 0 and space.pet_nutrition == 1:
                    # print(f'{space.id}:pet-mood-change')
                    from .actions import say
                    bot.send_message(space, f'🍽️🐕 {space.pet_name} is hungry. {say()}')
                pipe.hset(self.id, mapping={
                    'meadow_vegetable_growth':
                        min(space.meadow_vegetable_growth + 1, self.MEADOW_VEGETABLE_GROWTH_MAX),
                    'woods_growth': min(space.woods_growth + 1, self.WOODS_GROWTH_MAX),
                    'pet_nutrition': pet_nutrition,
                    'pet_fur': min(space.pet_fur + 1, self.PET_FUR_MAX),
                    'pet_activity_id': pet_activity_id
                })
                pipe.hincrby(self.id, 'time', 1)
            pipe.hgetall(self.id)

            data = await cast(Awaitable[list[dict[str, str]]], pipe.execute())
            space = Space(data[-1])

        pet = await self.get_pet()
        await pet.tick()
        for obj in await self.get_objects():
            await obj.tick(time + 1)

        if pet_activity_id and pet_activity_id not in {'', '💤', '🍃'}:
            obj = await bot.get_object(pet_activity_id)
            await obj.use()

        return space

    async def gather_meadow(self) -> list[str]:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split()
            growth = int(await pipe.hget(self.id, 'meadow_vegetable_growth') or '')
            pipe.multi()
            gathered = []
            if growth == self.MEADOW_VEGETABLE_GROWTH_MAX:
                gathered = ['🥕', '🪨']
                resources = sorted(resources + gathered, key=self._resource_order)
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
                resources = sorted(space.resources + wood, key=self._resource_order)
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
                resources = sorted(space.resources + wool, key=self._resource_order)
                pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'pet_fur': 0})
            await pipe.execute()
            return wool

    async def craft(self, typ: str) -> Object | str:
        bot = context.bot.get()
        try:
            cost = bot.costs[typ]
        except KeyError as e:
            raise ValueError(f'Unknown typ {typ}') from e
        if typ in bot.object_types:
            return await self._craft_home_item(typ, cost)
        return await self._craft_tool(typ, cost)

    async def _craft_tool(self, typ: str, cost: list[str]) -> str:
        async with transaction(context.bot.get().redis, self.id) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split(' ')
            tools = (await pipe.hget(self.id, 'tools') or '').split(' ')
            pipe.multi()
            if typ in tools:
                raise ValueError('already in tools')
            try:
                for resource in cost:
                    resources.remove(resource)
            except ValueError as e:
                raise ValueError('not enough resources') from e
            tools.append(typ)
            pipe.hset(self.id, mapping={'resources': ' '.join(resources), 'tools': ' '.join(tools)})
            await pipe.execute()
            return typ

    async def _craft_home_item(self, typ: str, cost: list[str]) -> Object:
        bot = context.bot.get()
        cls = bot.object_types[typ]
        id = f'Object:{randstr()}'

        items_key = f'{self.id}.items'
        async with transaction(bot.redis, self.id, items_key) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split(' ')
            item_count = await pipe.llen(items_key)
            pipe.multi()
            # TODO replace? random? require trash?
            #if item_count >= 4:
            #    raise ValueError('max items')
            try:
                for resource in cost:
                    resources.remove(resource)
            except ValueError as e:
                raise ValueError('not enough resources') from e
            pipe.hset(self.id, 'resources', ' '.join(resources))
            pipe.rpush(items_key, id)
            await pipe.execute()

        # Transaction note: paid and placeholder in list, so potentially we could call create later
        # to retry
        return await cls.create(id, typ)

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

    # TODO later: cook
    # TODO later: website
    # - after crafting furniture, set activity to new object - show std touch msg or something like
    # "feini is very curios"

    # wash_pet() pet_hygiene dirty

class Pet:
    MAX_DIRT = 48 + 1

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.space_id = data['space_id']
        self.dirt = int(data['dirt'])

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
