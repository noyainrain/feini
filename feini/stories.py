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

"""Short stories."""

from . import context
from .core import Entity
from .space import Event, Message, Pet, Space
from .util import randstr

class Story(Entity):
    """Short story.

    .. attribute:: space_id

       Related :class:`Space` ID.

    .. attribute:: chapter

       Current point in the story.

    .. attribute:: update_time

       Tick the chapter was updated at.
    """

    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.space_id = data['space_id']
        self.chapter = data['chapter']
        self.update_time = int(data['update_time'])

    async def get_space(self) -> Space:
        """Get the related space."""
        return await context.bot.get().get_space(self.space_id)

    async def tell(self) -> None:
        """Continue to the next point in the story if the relevant conditions are met."""
        raise NotImplementedError()

class IntroStory(Story):
    """Tutorial."""

    async def tell(self) -> None:
        bot = context.bot.get()
        async with bot.redis.pipeline() as pipe:
            await pipe.watch(self.id)
            chapter = await pipe.hget(self.id, 'chapter')
            if not chapter:
                raise ReferenceError(self.id)
            values = await pipe.hmget(self.space_id, 'resources', 'tools', 'pet_id')
            items = (values[0] or '').split()
            tools = (values[1] or '').split()
            pet_id = values[2]
            assert pet_id
            values = await pipe.hmget(pet_id, 'hatched', 'nutrition')
            hatched = bool(values[0])
            nutrition = int(values[1] or '')

            pipe.multi()
            if chapter == 'start':
                pipe.hset(self.id, mapping={'chapter': 'touch', 'update_time': bot.time})
                pipe.rpush('events', str(Event('space-explain-touch', self.space_id)))
            elif chapter == 'touch' and hatched:
                pipe.hset(self.id, mapping={'chapter': 'gather', 'update_time': bot.time})
                pipe.rpush('events', str(Event('space-explain-gather', self.space_id)))
            elif chapter == 'gather' and '🥕' in items:
                pipe.hset(self.id, mapping={'chapter': 'feed', 'update_time': bot.time})
                pipe.rpush('events', str(Event('space-explain-feed', self.space_id)))
            elif chapter == 'feed' and nutrition >= Pet.NUTRITION_MAX:
                pipe.hset(self.id, mapping={'chapter': 'craft', 'update_time': bot.time})
                pipe.rpush('events', str(Event('space-explain-craft', self.space_id)))
            elif chapter == 'craft' and '🪓' in tools:
                pipe.srem(f'{self.space_id}.stories', self.id)
                pipe.rpush('events', str(Event('space-explain-basics', self.space_id)))
            await pipe.execute()

class SewingStory(Story):
    """Story about sewing."""

    async def tell(self) -> None:
        bot = context.bot.get()
        async with bot.redis.pipeline() as pipe:
            await pipe.watch(self.id)
            values = await pipe.hmget(self.id, 'chapter', 'update_time')
            if not values:
                raise ReferenceError(self.id)
            chapter = values[0]
            update_time = int(values[1] or '')
            tools = (await pipe.hget(self.space_id, 'tools') or '').split()
            character_ids = await pipe.lrange(f'{self.space_id}.characters', 0, -1)
            character_ids = [character_id for character_id in character_ids
                             if await pipe.hget(character_id, 'avatar') == '👻']
            character_id = next(iter(character_ids), None)
            if character_id:
                message = Message.parse((await pipe.lrange(f'{character_id}.dialogue', 0, 0))[0])

            pipe.multi()
            if chapter == 'scissors' and '✂️' in tools:
                pipe.hset(self.id, mapping={'chapter': 'visit', 'update_time': bot.time})
            elif chapter == 'visit' and bot.time >= update_time + 2:
                character_id = f'Character:{randstr()}'
                pipe.hset(character_id,
                          mapping={'id': character_id, 'space_id': self.space_id, 'avatar': '👻'})
                dialogue = [
                    Message('initial'),
                    Message('ghost-sewing-hello'),
                    Message('ghost-sewing-daughter'),
                    Message('ghost-sewing-request', request=['🧶', '🧶', '🧶']),
                    Message('ghost-sewing-blueprint'),
                    Message('ghost-sewing-goodbye')
                ]
                pipe.rpush(f'{character_id}.dialogue', *(message.encode() for message in dialogue))
                pipe.rpush(f'{self.space_id}.characters', character_id)
                pipe.hset(self.id, mapping={'chapter': 'quest', 'update_time': bot.time})
                pipe.rpush('events', str(Event('space-visit-ghost', self.space_id)))
            elif (chapter == 'quest' and
                  message.id in {'ghost-sewing-blueprint', 'ghost-sewing-goodbye'}):
                pipe.zadd(f'{self.space_id}.blueprints', {'🪡': Space.BLUEPRINT_WEIGHTS['🪡']})
                pipe.hset(self.id, mapping={'chapter': 'leave', 'update_time': bot.time})
            elif chapter == 'leave' and message.id == 'ghost-sewing-goodbye':
                assert character_id
                pipe.delete(character_id, f'{character_id}.dialogue')
                pipe.lrem(f'{self.space_id}.characters', 1, character_id)
                pipe.srem(f'{self.space_id}.stories', self.id)
            await pipe.execute()
