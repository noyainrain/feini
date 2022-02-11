# TODO

"""TODO."""

from __future__ import annotations

from asyncio import get_event_loop, sleep, create_task
from contextlib import asynccontextmanager
from contextvars import ContextVar
import dataclasses
from dataclasses import dataclass
from datetime import datetime
import json
from logging import getLogger
import random
from typing import TypeVar, Type, cast, Awaitable, AsyncIterator, Callable
import unicodedata

from aioredis.exceptions import WatchError
from aiohttp import ClientSession, ClientError

from .util import Redis, Pipeline, JSONObject, randstr

bot: ContextVar[Bot] = ContextVar('bot')

class Space:
    MEADOW_VEGETABLE_GROWTH_MAX = 5
    PET_NUTRITION_MAX = 25

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.chat = data['chat']
        self.time = int(data['time'])
        self.resources = data['resources'].split()
        self.pet_name = data['pet_name']
        self.pet_nutrition = int(data['pet_nutrition'])
        self.meadow_vegetable_growth = int(data['meadow_vegetable_growth'])

    async def get_items(self) -> list[Item]:
        key = f'{self.id}.items'
        async with transaction(bot.get().redis, key) as pipe:
            item_ids = await pipe.lrange(key, 0, -1)
            pipe.multi()
            for item_id in item_ids:
                pipe.hgetall(item_id)
            items = await pipe.execute()
            return [Item(cast(dict[str, str], data)) for data in items]

    async def tick(self, time: int) -> Space:
        async with bot.get().redis.pipeline() as pipe:
            await pipe.watch(self.id) # type: ignore[misc]
            space = Space(await pipe.hgetall(self.id)) # type: ignore[misc]

            pipe.multi()
            if space.time == time:
                pet_nutrition = max(space.pet_nutrition - 1, 0)
                if pet_nutrition == 0 and space.pet_nutrition == 1:
                     print(f'{space.id}:pet-mood-change')
                pipe.hset(self.id, mapping={
                    'pet_nutrition': pet_nutrition,
                    'meadow_vegetable_growth': min(space.meadow_vegetable_growth + 1, self.MEADOW_VEGETABLE_GROWTH_MAX)
                })
                pipe.hincrby(self.id, 'time', 1)
            pipe.hgetall(self.id)

            data = await cast(Awaitable[list[dict[str, str]]], pipe.execute())
            return Space(data[-1])

    async def edit_pet_name(self, name: str) -> Space:
        async with bot.get().redis.pipeline() as pipe:
            pipe.hset(self.id, 'pet_name', name)
            pipe.hgetall(self.id)
            data = await cast(Awaitable[list[dict[str, str]]], pipe.execute())
            return Space(data[-1])

    async def feed_pet(self) -> None:
        async with transaction(bot.get().redis, self.id) as pipe:
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

    async def gather_meadow(self) -> list[str]:
        async with transaction(bot.get().redis, self.id) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split()
            growth = int(await pipe.hget(self.id, 'meadow_vegetable_growth') or '')
            pipe.multi()
            gathered = []
            if growth == self.MEADOW_VEGETABLE_GROWTH_MAX:
                gathered = ['🥕']
                pipe.hset(self.id, mapping={
                    'resources': ' '.join(resources + gathered),
                    'meadow_vegetable_growth': 0
                })
            await pipe.execute()
            return gathered

    async def craft(self, typ: str) -> None:
        try:
            cls = bot.get().item_types[typ]
            cost = ('🥕', '🥕')
        except KeyError as e:
            raise ValueError('TODO') from e
        id = f'Item:{randstr()}'

        items_key = f'{self.id}.items'
        async with transaction(bot.get().redis, self.id, items_key) as pipe:
            resources = (await pipe.hget(self.id, 'resources') or '').split(' ')
            item_count = await pipe.llen(items_key)
            pipe.multi()
            if item_count == 2:
                # TODO replace? random? require trash?
                raise ValueError('max items')
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
        await cls.create(id, typ)

    # TODO commit
    # TODO CONTINUE craft() -- OQ tools / items -- DRAFT which items and what
    # TODO CONTINUE pet_activity play/sleep
    # TODO CONTINUE events (hungry)
    # TODO CONTINUE pet_sleep
    # TODO CONTINUE wash_pet() pet_hygiene dirty

class Item:
    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']
        self.type = data['type']

    @staticmethod
    async def create(id: str, typ: str) -> Item:
        data = {'id': id, 'item_type': typ}
        bot.get().redis.hset(id, mapping=data)
        return Item(data)

    async def tick(self, time: int) -> None:
        pass

class Plant(Item):
    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(id: str, typ: str) -> Plant:
        data = {'id': id, 'item_type': '🪴', 'state': '🪴'}
        bot.get().redis.hset(id, mapping=data)
        return Plant(data)

    async def tick(self, time: int) -> None:
        if time % 24 == 0:
            await bot.get().redis.hset(self.id, 'state', random.choice(['🪴', '🌺']))

class Palette(Item):
    def __init__(self, data: dict[str, str]) -> None:
        super().__init__(data)
        self.state = data['state']

    @staticmethod
    async def create(id: str, typ: str) -> Palette:
        data = {'id': id, 'item_type': '🎨', 'state': '🎨'}
        bot.get().redis.hset(id, mapping=data)
        return Palette(data)

    async def tick(self, time: int) -> None:
        if time % 24 == 0:
            await bot.get().redis.hset(self.id, 'state', random.choice(['🎨', '🖼️']))

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

class Bot:
    def __init__(self, *, telegram_key: str | None = None) -> None:
        self.telegram_key = telegram_key
        self.time = 0

        self.redis = cast(Redis, Redis.from_url('redis://localhost', decode_responses=True))
        self._base = f'https://api.telegram.org/bot{self.telegram_key}'

        commands: dict[tuple[str, ...], Callable[[Space, str], Awaitable[str]]] = {
            ('👋', '🤚'): self._touch,
            ('🥕', ): self._feed_pet,
            ('🧺', ): self._gather_meadow,
            ('✏️', ): self._edit_pet_name
        }
        self._commands = {
            emoji: f for emojis, f in commands.items() for emoji in emojis
        }
        self.item_types = {
            '⛲': Item,
            '🪴': Plant,
            '🎨': Palette
        }

    async def run(self) -> None:
        print('STARTING BOT')
        bot.set(self)

        # get_event_loop().create_task(self._handle())
        create_task(self._handle())
        #TICK = 60 * 60
        #TICK = 1
        TICK = 30

        now = datetime.now().timestamp()
        now = now // TICK

        while True:
            self.time = int(datetime.now().timestamp() / TICK)
            getLogger().info('Tick %s', self.time)

            space_ids = await cast(Awaitable[list[str]], self.redis.hvals('spaces_by_chat'))
            for space_id in space_ids:
                #space = Space(
                #    await cast(Awaitable[dict[str, str]], self.redis.hgetall(f'Space:{space_id}')))
                space = await self.get_space(space_id)
                while space.time < self.time:
                    space = await space.tick(space.time)
                    print(space.id, space.pet_name, space.time, space.pet_nutrition,
                          space.meadow_vegetable_growth)

            await sleep((self.time + 1) * TICK - datetime.now().timestamp())

        #time = int(await cast('Awaitable[str | None]', self.redis.get('time')) or '0')
        #await self.redis.set('time', time) # type: ignore[misc]

    async def _handle_command(self, chat: str, text: str) -> str:
        space_id = await self.redis.hget('spaces_by_chat', chat)
        if space_id:
            space = await self.get_space(space_id)
        else:
            getLogger().info('Yay, new space!')
            space = await self.create_space(chat)

        tokens = self._parse(text)
        print(repr(text), repr(tokens))
        getLogger().info("%s @%s", ' '.join(tokens), space.id)

        f = self._commands.get(tokens[0], self._usage)
        return await f(space, *tokens[1:])

    async def get_space(self, id: str) -> Space:
        return Space(await cast(Awaitable[dict[str, str]], self.redis.hgetall(id)))

    async def create_space(self, chat: str) -> Space:
        async with self.redis.pipeline() as pipe:
            #time = await cast(Awaitable[str], pipe.get('time'))
            data = {
                'id': f'Space:{randstr()}',
                'chat': chat,
                'time': str(self.time),
                'resources': '',
                'pet_name': 'Feini',
                'pet_nutrition': '0',
                'meadow_vegetable_growth': '5'
            }
            pipe.hset(data['id'], mapping=data)
            pipe.hset('spaces_by_chat', chat, data['id'])
            await pipe.execute()
            return Space(data)

    async def _touch(self, space: Space, *args: str) -> str:
        return '🐕 “Woof!”'

    async def _feed_pet(self, space: Space, *args: str) -> str:
        try:
            await space.feed_pet()
            return f'🥕🐕 {space.pet_name} enjoys its veggies. 😊'
        except ValueError as e:
            if 'resources' in str(e):
                return 'You do not have any 🥕 at the moment.'
            if 'pet_nutrition' in str(e):
                return f'🐕 {space.pet_name} seems full and ignores the 🥕.'
            raise

    async def _gather_meadow(self, space: Space, *args: str) -> str:
        resources = await space.gather_meadow()
        if resources:
            return f"🧺 You gathered {''.join(resources)} from the meadow. 😊"
        return '🧺 The meadow was empty. Maybe try again later?'

    async def _edit_pet_name(self, space: Space, *args: str) -> str:
        if len(args) < 1 or unicodedata.category(args[0][0]) == 'So':
            return '✏ NAME' # TODO
        space = await space.edit_pet_name(args[0])
        return f'🐕 {space.pet_name} seems to like its new name.'

    async def _usage(self, space: Space, *args: str) -> str:
        return f'🐕 {space.pet_name} seems confused.\n\n(Try 👋)'

    def _parse(self, command: str) -> list[str]:
        if not command:
            return []
        if unicodedata.category(command[0]) == 'So':
            if len(command) >= 2 and command[1] in '\ufe0e\ufe0f':
                return [command[:2]] + self._parse(command[2:])
            return [command[0]] + self._parse(command[1:])
        #index = len(command)
        #for i, c in enumerate(command):
        #    if unicodedata.category(c) == 'So':
        #        index = i
        #        break
        i = 0
        while i < len(command) and unicodedata.category(command[i]) != 'So':
            i = i + 1
        return [command[:i]] + self._parse(command[i:])

    #@staticmethod
    #def _parse(command: str) -> list[str]:
    #    tokens: list[str] = []
    #    text: list[str] = []
    #    emoji: list[str] = []
    #    for c in command:
    #        if emoji:
    #            if c in '\ufe0e\ufe0f': # Emoji variation sequence
    #                emoji.append(c)
    #                tokens.append(''.join(emoji))
    #                emoji = []
    #                continue
    #            else:
    #                tokens.append(''.join(emoji))
    #                emoji = []

    #        print(c, ord(c))
    #        if unicodedata.category(c) = 'So':
    #            if text:
    #                tokens.append(''.join(text).strip())
    #                text = []
    #            tokens.append(c)
    #        else:
    #            text.append(c)
    #    if text:
    #        tokens.append(''.join(text).strip())
    #    return tokens

    async def _handle(self) -> None:
        #import sys
        #for i in range(0, sys.maxunicode):
        #    c = chr(i)
        #    if unicodedata.category(c) == 'So':
        #        print(c, end='')

        loop = get_event_loop()
        self._client = ClientSession()

        async for user_id, text in self._updates():
            if user_id and text:
                try:
                    reply = await self._handle_command(str(user_id), text)
                except Exception as e:
                    getLogger().exception('Gateway error')
                    reply = '⚠ OMG sorry, fatal error, we will fix it!'
                loop.create_task(self._reply(user_id, reply))

        print('HANDLE EXIT')
        await self._client.close()

    async def _updates(self) -> AsyncIterator[tuple[int, str]]:
        # TODO load offset
        offset = 0

        while True:
            try:
                url = f'{self._base}/getUpdates?timeout=360&offset={offset}'
                # print(url)
                t = datetime.now()
                response = await self._client.get(url, raise_for_status=True)
                data = await cast(Awaitable[object], response.json())
                print(response.status, data, datetime.now() - t)
                if not isinstance(data, dict):
                    raise TypeError()
                result = JSONObject(data)
                updates: list[tuple[int, int | None, str | None]] = []
                for data in result.get('result', list):
                    if not isinstance(data, dict):
                        raise TypeError()
                    update = JSONObject(data)
                    update_id = update.get('update_id', int)
                    message = update.get('message', JSONObject, optional=True)
                    if message:
                        yield (message.get('from', JSONObject).get('id', int),
                               message.get('text', str))
                    # TODO store offset
                    offset = update_id + 1

            except (ClientError, TypeError) as e:
                print('TMP GET ERROR, RETRYING...', e)
                await sleep(1)

    async def _reply(self, user_id: int, text: str) -> None:
        while True:
            try:
                body = {'chat_id': user_id, 'text': text}
                response = await self._client.post(f'{self._base}/sendMessage', json=body,
                                                   raise_for_status=True)
                await response.read()
                break
            except ClientError as e:
                print('TMP REPLY ERROR, RETRYING...', e)
                await sleep(1)

#class Telegram:
#    @dataclass
#    class Update:
#        update_id: int
#        message: Telegram.Message
#
#        @staticmethod
#        def parse(data: dict[str, object]) -> Telegram.Update:
#            update_id = data['update_id']
#            message_data = data['message']
#            if not isinstance(update_id, int):
#                raise TypeError(update_id, type(update_id))
#            if not isinstance(message_data, dict):
#                raise TypeError()
#            return Telegram.Update(update_id, Telegram.Message.parse(message_data))
#
#    @dataclass
#    class Message:
#        frm: Telegram.User
#        text: str
#
#        @staticmethod
#        def parse(data: dict[str, object]) -> Telegram.Message:
#            frm = data.get('from')
#            text = data.get('text')
#            if not isinstance(frm, dict):
#                raise TypeError()
#            if not isinstance(text, str):
#                raise TypeError()
#            return Telegram.Message(Telegram.User.parse(frm), text)
#
#    @dataclass
#    class User:
#        id: int
#
#        @staticmethod
#        def parse(data: dict[str, object]) -> Telegram.User:
#            id = data['id']
#            if not isinstance(id, int):
#                raise TypeError()
#            return Telegram.User(id)

#class Space:
#    def __init__(self, data: JSON) -> None:
#        x = JSONObject(data)
#        self.id = x.get('id', str)
#        self.chat = x.get('chat', str)
#        self.pet_name = x.get('pet_name', str)
#
#    def json(self) -> JSON:
#        return {'id': self.id, 'chat': self.chat, 'pet_name': self.pet_name}
#
#    async def edit_pet_name(self, bot: Bot, name: str) -> Space:
#        data = await rpatch(self.id, {'pet_name': name}, bot.redis)
#        return Space(data)
#
#async def rpatch(id: str, patch: JSON, redis: Redis) -> JSON:
#    f = redis.register_script("""
#        local id, patch = unpack(KEYS), unpack(ARGV)
#        patch = cjson.decode(patch)
#        local object = cjson.decode(redis.call("GET", id))
#        for name, value in ipairs(patch) do
#            object[name] = value
#        end
#        object = cjson.encode(object)
#        redis.call("SET", id, object)
#        return object
#    """)
#    result = await cast(Awaitable[object], f([id], [json.dumps(patch)]))
#    assert isinstance(result, bytes)
#    data = cast(object, json.loads(result))
#    assert isinstance(data, dict)
#    return data

#_T = TypeVar('_T')

#def get_json(data: object, key: str, cls: Type[_T]) -> _T:
#    if not isinstance(data, dict):
#        raise TypeError()
#    value = data[key]
#    if not isinstance(value, cls):
#        raise TypeError()
#    return value

#JSON = dict[str, object]

#@dataclass
#class Space:
#    id: str
#    chat: str
#    pet_name: str
#
#    async def edit_pet_name(self, bot: Bot, name: str) -> Space:
#        await cast(Awaitable[object], bot.redis.hset(f'Space:{self.id}', 'pet_name', name))
#        return dataclasses.replace(self, pet_name=name)
