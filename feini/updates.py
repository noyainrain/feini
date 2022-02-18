from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from logging import getLogger

from . import context
from .util import randstr

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
