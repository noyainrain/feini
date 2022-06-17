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

"""Database updates, ordered from latest to earliest."""

# pylint: disable=missing-function-docstring

# Note that updates are applied before the bot is started, thus there are no race conditions.

from logging import getLogger

from . import context
from .space import Space
from .util import randstr

async def update_space_stories() -> None:
    updates = 0
    bot = context.bot.get()
    redis = bot.redis
    for space_id in await redis.hvals('spaces_by_chat'):
        chapter = await redis.hget(space_id, 'story')
        if chapter is not None:
            async with redis.pipeline() as pipe:
                pipe.multi()
                stories = [{
                    'id': f'SewingStory:{randstr()}',
                    'space_id': space_id,
                    'chapter': 'scissors',
                    'update_time': str(bot.time)
                }]
                if chapter:
                    stories.append({
                        'id': f'IntroStory:{randstr()}',
                        'space_id': space_id,
                        'chapter': chapter,
                        'update_time': str(bot.time)
                    })
                for story in stories:
                    pipe.hset(story['id'], mapping=story)
                    pipe.sadd(f'{space_id}.stories', story['id'])
                pipe.hdel(space_id, 'story')
                await pipe.execute()
                updates += 1
    if updates:
        getLogger(__name__).info('Updated Space.stories (%d)', updates)

async def update_space_blueprints() -> None:
    updates = 0
    redis = context.bot.get().redis
    blueprints = {
        blueprint:
            Space.BLUEPRINT_WEIGHTS[blueprint]
            for blueprint
            in ['🪓', '✂️', '🍳', '🚿', '🧭', '🪃', '⚾', '🧸', '🛋️', '🪴', '⛲', '📺', '🗞️', '🎨']
    }
    for space_id in await redis.hvals('spaces_by_chat'):
        key = f'{space_id}.blueprints'
        if not await redis.exists(key):
            await redis.zadd(key, blueprints)
            updates += 1
    if updates:
        getLogger(__name__).info('Updated Space.blueprints (%d)', updates)

async def update_pet_clothing() -> None:
    updates = 0
    redis = context.bot.get().redis
    for space_id in await redis.hvals('spaces_by_chat'):
        pet_id = await redis.hget(space_id, 'pet_id') or ''
        if not await redis.hexists(pet_id, 'clothing'):
            await redis.hset(pet_id, 'clothing', '')
            updates += 1
    if updates:
        getLogger(__name__).info('Updated Pet.clothing (%d)', updates)

async def update_space_trail_supply() -> None:
    updates = 0
    bot = context.bot.get()
    for space_id in await bot.redis.hvals('spaces_by_chat'):
        if not await bot.redis.hexists(space_id, 'trail_supply'):
            async with bot.redis.pipeline() as pipe:
                pipe.hset(space_id, 'trail_supply', Space.TRAIL_SUPPLY_FULL)
                pipe.rpush('events', f'space-stroll-compass-blueprint {space_id}')
                await pipe.execute()
                updates += 1
    if updates:
        getLogger(__name__).info('Updated Space.trail_supply (%d)', updates)

# /clean

# UpdateFunction = Callable[[], Awaitable[None]]

#class update:
#    def __init__(self, f: Callable[[], Awaitable[None]]) -> None:
#        self.f = f
#
#    async def __call__(self) -> None:
#        await self.f()

#class update:
#    def __init__(self, label: str, _f: UpdateFunction | None = None) -> None:
#        self.label = label
#        self._f = _f
#
#    def __call__(self, f: UpdateFunction) -> update:
#        return update(self.label, f)
#
#    async def apply(self) -> None:
#        if not self._f:
#            raise TypeError()
#        await self._f()

#def update(label: str) -> Callable[[UpdateFunction], Update]:
#    return partial(Update, label=label)

#@update('oink')

async def update_pet_dirt() -> None:
    bot = context.bot.get()
    updates = 0
    space_ids = await bot.redis.hvals('spaces_by_chat')
    for space_id in space_ids:
        tools = (await bot.redis.hget(space_id, 'tools') or '').split()
        if '🧽' not in tools:
            async with bot.redis.pipeline() as pipe:
                tools.insert(4, '🧽')
                pet_data = {'id': f'Pet:{randstr()}', 'space_id': space_id, 'dirt': '0'}
                pipe.hset(space_id, mapping={'tools': ' '.join(tools), 'pet_id': pet_data['id']})
                pipe.hset(pet_data['id'], mapping=pet_data)
                pipe.rpush('events', f'space-stroll-sponge {space_id}')
                await pipe.execute()
            updates += 1
    if updates:
        getLogger(__name__).info('Updated Pet.dirt (%d)', updates)

#async def update_pen() -> None:
#    bot = context.bot.get()
#    version = tuple(int(c) for c in (await bot.redis.get('version') or '0.0.0').split('.'))
#    space_ids = []
#    if version < (0, 0, 1):
#        space_ids = await bot.redis.hvals('spaces_by_chat')
#        async with bot.redis.pipeline() as pipe:
#            pipe.rpush('events', *(f'{id}.update-pen' for id in space_ids))
#            pipe.set('version', '0.0.1')
#            await pipe.execute()
#            getLogger(__name__).info('Updated pen behaviour: %d', len(space_ids))

#reveal_type(update_pen)
