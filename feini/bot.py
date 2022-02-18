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

from asyncio import get_event_loop, sleep, create_task
from datetime import datetime
from logging import getLogger
from typing import Awaitable, AsyncIterator, Callable, cast
import unicodedata

from aiohttp import ClientSession, ClientError

from .actions import (
    Action, touch, feed_pet, gather_meadow, craft, change_pet_name, view_tent, chop_wood, shear_pet,
    usage, view_sleep, view_leaves, view_boomerang, view_ball, view_teddy, view_couch, view_plant,
    view_fountain, view_television, view_newspaper, view_palette, wash_pet)
from . import actions, context, updates
from .items import Newspaper, Object, Plant, Palette, Television
from .space import Pet, Space
from .util import Redis, JSONObject, isemoji, randstr

class Story:
    def __init__(self) -> None:
        pass

    # bot.send_message(space, f'ℹ️  You can give it a name with ✏️, e.g. ✏️ Feini.')
    async def update(self, space: Space) -> None:
        bot = context.bot.get()
        async with bot.redis.pipeline() as pipe:
            await pipe.watch(space.id)
            space = Space(await pipe.hgetall(space.id))
            pipe.multi()
            if space.story == 'touch' and not space.pet_is_egg:
                pipe.hset(space.id, 'story', 'gather')
                bot.send_message(space, f'ℹ️  {space.pet_name} seems hungry. You can gather some veggies with 🧺.')
            elif space.story == 'gather' and '🥕' in space.resources:
                pipe.hset(space.id, 'story', 'feed')
                bot.send_message(space, f'ℹ️  You can now feed {space.pet_name} with 🥕.')
            elif space.story == 'feed' and space.pet_nutrition == Space.PET_NUTRITION_MAX:
                pipe.hset(space.id, 'story', 'craft')
                bot.send_message(
                    space,
                    f'ℹ️  You can craft tools and furniture for {space.pet_name} with 🔨. You can currently afford to craft an axe with 🔨🪓.')
            elif space.story == 'craft' and '🪓' in space.tools:
                pipe.hset(space.id, 'story', '')
                bot.send_message(
                    space,
                    f'ℹ️  All items are placed in the tent. You can view it with ⛺. You can watch and pet {space.pet_name} any time with 👋.')
            await pipe.execute()

class Bot:
    def __init__(self, *, redis_url: str = 'redis:', telegram_key: str | None = None) -> None:
        self.telegram_key = telegram_key
        self.time = 0

        self.redis = cast(Redis, Redis.from_url(redis_url, decode_responses=True))
        self._base = f'https://api.telegram.org/bot{self.telegram_key}'

        # commands: dict[tuple[str, ...], Callable[[Space, str], Awaitable[str]]] = {
        self._commands: dict[str, Action] = {
            '⛺': view_tent,
            '🧺': gather_meadow,
            '🪓': chop_wood,
            '🔨': craft,
            '👋': touch,
            '🥕': feed_pet,
            '🧽': wash_pet,
            '✂️': shear_pet,
            '✏️': change_pet_name
        }

        self.activities: dict[str, Callable[[Space, Object | str], Awaitable[str]]] = {
        #self.activities = {
            '💤': view_sleep,
            '🍃': view_leaves,
            '🪃': view_boomerang,
            '⚾': view_ball,
            '🧸': view_teddy,
            '🛋️': view_couch,
            '🪴': view_plant,
            '⛲': view_fountain,
            '📺': view_television,
            '🗞️': view_newspaper,
            '🎨': view_palette
        }

        #self._commands = {
        #    emoji: f for emojis, f in commands.items() for emoji in emojis
        #}

        # see https://unicode.org/emoji/charts/emoji-variants.html
        alternatives = {
            '👋': ['👋\N{VARIATION SELECTOR-16}', '🤚', '🤚\N{VARIATION SELECTOR-16}', '🖐️', '🖐︎',
                   '✋', '✋\N{VARIATION SELECTOR-16}'],
            '✏️': ['✏', '🖊️', '🖊'],
            '🔨': ['⚒️', '⚒', '🛠️', '🛠'],
            '🧽': ['🧴', '🧼'],
            '✂️': ['✂'],
            '🪃': ['🥏'],
            '⚾': ['⚾\N{VARIATION SELECTOR-16}', '🥎'],
            '🛋️': ['🛋'],
            '⛲': ['⛲\N{VARIATION SELECTOR-16}'],
            '📺': ['📺\N{VARIATION SELECTOR-16}'],
            '🗞️': ['🗞', '📰'],
            '⛺': ['⛺\N{VARIATION SELECTOR-16}', '🏕️', '🏕']
        }
        self.alternatives = {
            alt: can for can, alts in alternatives.items() for alt in alts
        }
        #print('ALTERNATIVES', self.alternatives)

        self.object_types = {
            # Toys
            '🪃': Object,   # simple
            '⚾': Object,   # simple
            '🧸': Object,   # simple
            # Furniture
            '🛋️': Object,   # simple
            '🪴': Plant,  # state
            '⛲': Object,   # simple
            # CE
            '📺': Television,   # variation
            # Other
            '🗞️': Newspaper,   # variation
            '🎨': Palette # state
        }

        self.costs = {
        	# Tools
            '🪓': ['🪨'], # S, 1 d
            '✂️': ['🪨', '🪨', '🪨'],  # S, 3 d
            '🍳': ['🪨', '🪨', '🪨', '🪨'], # S, 4 d
            '🚿': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'], # M, 4 d
            # Toys
            '🪃': ['🪵', '🪵'], # S, 2 d
            '⚾': ['🪵', '🧶', '🧶', '🧶'], # S, 3 d
            '🧸': ['🧶', '🧶', '🧶', '🧶'], # S, 4 d
            # Furniture
            '🛋️': ['🪨', '🪵', '🪵', '🪵', '🪵', '🧶', '🧶', '🧶', '🧶'], # L, 4 d
            '🪴': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'],  # M, 4 d
            '⛲': ['🪨', '🪨', '🪨', '🪨', '🪨', '🪨', '🪨'], # L, 7 d
            # Devices
            '📺': ['🪨', '🪨', '🪵', '🪵', '🪵', '🪵'], # M 4 d
            # Miscellaneous
            '🗞️': ['🪵', '🪵', '🧶', '🧶'], # S, 2 d
            '🎨': ['🪵', '🪵', '🪵', '🪨', '🧶', '🧶', '🧶'] # M, 3 d
        }

        ## with sizes:
        ##       S       M       L
        ##slots: 5 * 2 + 4 * 3 + 2 * 4 = 30
        ##30 slots
        ##=> 2.2 per slot
        #CRAFT_INTERVAL = 2
        #costs = {typ: list(cost) for typ, cost in self.costs.items()}
        #del costs['🪓']
        #del costs['🪃']
        #from itertools import chain
        #merged = list(chain(*costs.values())) #cost for cost in self.costs.values()]
        #dist = {resource: merged.count(resource) for resource in ('🪨', '🪵', '🧶')}
        #income = {'🪨': 1, '🪵': 1, '🧶': 1}
        #sum_income = sum(income.values())
        #item_count = len(costs)
        #print('Items:', item_count)
        #print('Income:', sum_income, '/ d')
        #print('Target craft interval:', CRAFT_INTERVAL, 'd')
        #print('=> Distribute resources:', item_count * sum_income * CRAFT_INTERVAL)
        #print('=> Resources / item:', sum_income * CRAFT_INTERVAL)
        #print('---')
        #for resource, count in dist.items():
        #    expected = income[resource] * item_count * CRAFT_INTERVAL
        #    print(resource * count, count, '/', expected)
        #print('avg craft interval:', len(merged) / sum_income / len(costs), 'd')
        #max_resource = ''
        #max_count = 0
        #for resource, count in dist.items():
        #    if count > max_count:
        #        max_resource = resource
        #        max_count = count
        #print('max craft interval:', max_resource, max_count / income[max_resource] / item_count,
        #      'd')

    async def update(self) -> None:
        from inspect import iscoroutinefunction, signature
        for name, f in cast(dict[str, object], vars(updates)).items():
            if name.startswith('update_'):
                assert iscoroutinefunction(f) and not signature(f).parameters # type: ignore[arg-type]
                await cast(Callable[[], Awaitable[None]], f)()

                # Will fail with with a TypeError if f is not callable or takes any arguments or
                # does not return a
                # Will fail with TypeError, that's fine
                # await f() # type: ignore[misc,operator]


        #reveal_type(x)
        #x = await cast(Callable[[], Awaitable[None]], f)()
        #assert iscoroutinefunction(f)
        #x = await cast(Callable[[], Awaitable[None]], f)()
        #reveal_type(x)
        #x = cast(object, f())
        #assert isawaitable(x)
        #await x
        #reveal_type(x)
        #version = tuple(int(c) for c in (await self.redis.get('version') or '0.0.0').split('.'))
        #if version < (0, 0, 1):
        #    space_ids = await self.redis.hvals('spaces_by_chat')
        #    for space_id in space_ids:
        #        space = Space(await self.redis.hgetall(space_id))
        #        self.send_message(space, '✏️ Your pen is working again.')
        #    await self.redis.set('version', '0.0.1')
        #version = tuple(int(c) for c in (await self.redis.get('version') or '0.0.0').split('.'))
        #if version < (0, 0, 1):
        #    space_ids = await self.redis.hvals('spaces_by_chat')
        #    async with self.redis.pipeline() as pipe:
        #        pipe.rpush('events', *(f'{id}.update-pen' for id in space_ids))
        #        pipe.set('version', '0.0.1')
        #        await pipe.execute()

    @staticmethod
    async def space_update_pen(space: Space) -> str:
        return '✏️ Your pen is working again.'

    @staticmethod
    async def space_pet_is_hungry(space: Space) -> str:
        return f'🍽️🐕 {space.pet_name} is hungry. {say()}'

    async def run(self) -> None:
        print('STARTING BOT')
        context.bot.set(self)

        await self.update()

        # get_event_loop().create_task(self._handle())
        create_task(self._handle_events())
        create_task(self._handle())
        TICK = 60 * 60

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
                    #print(
                    #    space.id, space.pet_name, space.time, 'M', space.meadow_vegetable_growth,
                    #    'W', space.woods_growth, 'F', space.pet_fur, 'N', space.pet_nutrition)
                    ##    [item.type for item in await space.get_objects()])

            await sleep((self.time + 1) * TICK - datetime.now().timestamp())

        #time = int(await cast('Awaitable[str | None]', self.redis.get('time')) or '0')
        #await self.redis.set('time', time) # type: ignore[misc]

    async def _handle_command(self, chat: str, text: str) -> str:
        space_id = await self.redis.hget('spaces_by_chat', chat)
        if space_id:
            space = await self.get_space(space_id)
        else:
            space = await self.create_space(chat)
            getLogger().info('New space @%s %s', space.id, space.pet_name)
            self.send_message(space, 'ℹ️  You can touch the egg by sending a 👋 emoji. What will happen?')
            return '🥚 You found an egg. 😮'

        tokens = self._parse(text)
        tokens = [self.alternatives.get(token, token) for token in tokens]
        getLogger().info("%s @%s %s", ' '.join(tokens), space.id, space.pet_name)

        item = tokens[0]
        available = {*space.resources, *space.tools,
                     *(obj.type for obj in await space.get_objects()), '⛺'}
        if item not in available:
            word = item if isemoji(item) else f'“{item}”'
            return f'You have no {word} at the moment. Maybe have a look in the ⛺?'

        f = self._commands.get(item, usage)
        reply = await f(space, *tokens)

        await Story().update(space)

        return reply

    async def get_space(self, id: str) -> Space:
        return Space(await self.redis.hgetall(id))

    async def get_object(self, id: str) -> Object:
        data = await self.redis.hgetall(id)
        return self.object_types[data['type']](data)

    async def create_space(self, chat: str) -> Space:
        async with self.redis.pipeline() as pipe:
            #time = await cast(Awaitable[str], pipe.get('time'))
            space_id = f'Space:{randstr()}'
            pet_id = f'Pet:{randstr()}'
            data = {
                'id': space_id,
                'chat': chat,
                'time': str(self.time),
                'resources': '',
                # in reverse order: care, gather, craft, other
                'tools': '👋 ✏️ 🔨 🧺 🧽',
                'meadow_vegetable_growth': str(Space.MEADOW_VEGETABLE_GROWTH_MAX),
                'woods_growth': str(Space.WOODS_GROWTH_MAX),
                'pet_id': pet_id,
                'pet_name': 'Feini',
                'pet_is_egg': 'true',
                'pet_nutrition': str(Space.INTERVAL_S),
                'pet_fur': '0',
                'pet_activity_id': '',
                'story': 'touch'
            }
            pet_data = {
                'id': pet_id,
                'space_id': space_id,
                'dirt': str(Pet.MAX_DIRT - Space.INTERVAL_S)
            }
            pipe.hset(space_id, mapping=data)
            pipe.hset(pet_id, mapping=pet_data)
            pipe.hset('spaces_by_chat', chat, data['id'])
            await pipe.execute()
            return Space(data)

    def _parse(self, command: str) -> list[str]:
        if not command:
            return []
        category = unicodedata.category(command[0])
        if category.startswith('Z'): # space
            return self._parse(command[1:]) # could optimize by eliminating whole run
        if category == 'So':
            if len(command) >= 2 and command[1] in '\ufe0e\ufe0f':
                return [command[:2]] + self._parse(command[2:])
            return [command[0]] + self._parse(command[1:])
        #index = len(command)
        #for i, c in enumerate(command):
        #    if unicodedata.category(c) == 'So':
        #        index = i
        #        break
        i = 0
        while not (category == 'So' or category.startswith('Z')):
            i = i + 1
            if i >= len(command):
                break
            category = unicodedata.category(command[i])
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

    async def _handle_events(self) -> None:
        #event_messages = {}
        #for event_message in cast(dict[str, object], vars(actions)).values():
        #    if isinstance(event_message, actions.EventMessageFunc):
        #        event_messages[event_message.event_type] = event_message
        members = cast(dict[str, object], vars(actions)).values()
        event_messages = {
            member.event_type:
                member for member in members if isinstance(member, actions.EventMessageFunc)
        }

        # self._event_handlers: dict[str, Callable[[Space], Awaitable[str]]] = {}

        while True:
            _, event = await self.redis.blpop('events')
            event_type, space_id = event.split()
            space = await self.get_space(space_id)
            f = event_messages[event_type]
            try:
                reply = await f(space)
            except Exception as e:
                getLogger().exception('EVENT HANDLER ERROR')
            else:
                self.send_message(space, reply)

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
                # print(response.status, data, datetime.now() - t)
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

    def send_message(self, space: Space, text: str) -> None:
        async def f() -> None:
            await sleep(1)
            await self._reply(int(space.chat), text)
        get_event_loop().create_task(f())

    async def _reply(self, user_id: int, text: str) -> None:
        while True:
            try:
                body = {'chat_id': user_id, 'text': text}
                response = await self._client.post(f'{self._base}/sendMessage', json=body) #, raise_for_status=True)
                detail = await response.text()
                if not response.ok:
                    getLogger(__name__).warning('TMP REPLY ERROR HTTP %d (%s)', response.status, detail)
                    await sleep(1)
                    continue
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

#2x
#🧶🧶🧶🧶🧶🧶🧶🧶
#🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵
#🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨
#	
#4x
#🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶
#🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵
#🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨
#
#6x (yarn / 2 days)
#⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶⬜🧶
#🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵
#🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨
#
#6x
#🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶
#🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵
#🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨
#
#11(12) items = 22d
#6x with sizes S & M & L
#🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶🧶⬜⬜⬜⬜⬜⬜
#🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵🪵
#🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨🪨
#
#goal: craft / 2 days
#5 (rock, wood, 1 yarn) resourcen / day
#=> 5 resources / item
#2 sizes: S & L(incl M)
#
#11 items
#22 days
#66 resources

#'🕛': Object,   # Cha
#'🔮': Object,   # Var
            #'🕛': [
            #    '🕛\N{VARIATION SELECTOR-16}', '🕐', '🕐\N{VARIATION SELECTOR-16}', '🕑',
            #    '🕑\N{VARIATION SELECTOR-16}', '🕒', '🕒\N{VARIATION SELECTOR-16}', '🕓',
            #    '🕓\N{VARIATION SELECTOR-16}', '🕔', '🕔\N{VARIATION SELECTOR-16}', '🕕',
            #    '🕕\N{VARIATION SELECTOR-16}', '🕖', '🕖\N{VARIATION SELECTOR-16}', '🕗',
            #    '🕗\N{VARIATION SELECTOR-16}', '🕘', '🕘\N{VARIATION SELECTOR-16}', '🕙',
            #    '🕙\N{VARIATION SELECTOR-16}', '🕚', '🕚\N{VARIATION SELECTOR-16}', '🕰️',
            #    '🕰️\N{VARIATION SELECTOR-16}']
