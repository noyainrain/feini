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

"""Open Feini chatbot."""

# /clean

from __future__ import annotations

import asyncio
from asyncio import CancelledError, Queue, shield, sleep, create_task
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import json
from json import JSONDecodeError
from logging import getLogger
from typing import Awaitable, AsyncIterator, Callable, cast
import unicodedata
from urllib.parse import urljoin

from aiohttp import ClientError, ClientPayloadError, ClientSession, ClientTimeout

from .actions import (
    MainMode, Mode, view_sleep, view_leaves, view_boomerang, view_ball, view_teddy, view_couch,
    view_plant, view_fountain, view_television, view_newspaper, view_palette)
from . import actions, context, updates
from .furniture import Furniture, FURNITURE_TYPES
from .space import Pet, Space
from .util import Redis, JSONObject, cancel, raise_for_status, randstr, recovery

class Bot:
    """Open Feini chatbot.

    .. attribute:: time

       TODO.

    .. attribute:: redis

       Redis database.

    .. attribute:: redis_url

       TODO.

    .. attribute:: debug

       Indicates if debug mode is enabled.
    """

    def __init__(self, *, redis_url: str = 'redis:', debug: bool = False,
                 telegram_key: str | None = None) -> None:
        self.time = 0
        self.redis_url = redis_url
        self.debug = debug
        # TODO handle redis_url error
        # TODO handle redis errors (in all event loops)
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.http = ClientSession(timeout=ClientTimeout(total=20))
        self.telegram = Telegram(telegram_key) if telegram_key else None

        self._chat_modes: dict[str, Mode] = {}
        self._outbox: Queue[Message] = Queue()

        # TODO move to actions / mode
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

        # TODO in actions.py: (use on first action arg and match with actions, so maybe in Mode)
        #def normalize_emoji(emoji: str) -> str:
        #    """TODO. emoji variations, multiple emojis expressing the same concept and text alias.
        #    normalize. *emoji* may also be a text representation"""
        #    try:
        #        return _EMOJI_VARIANTS[emoji]
        #    except KeyError:
        #        return emoji
        # https://unicode.org/emoji/charts/text-style.html
        # https://unicode.org/emoji/charts/emoji-list.html
        alternatives = {
            '🎧': ['🎧\N{VARIATION SELECTOR-15}', '🎧\N{VARIATION SELECTOR-16}'],
            '👓': ['👓\N{VARIATION SELECTOR-15}', '👓\N{VARIATION SELECTOR-16}'],
            '🕶️': ['🕶', '🕶\N{VARIATION SELECTOR-15}'],
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
            '⛺': ['⛺\N{VARIATION SELECTOR-16}', '🏕️', '🏕'],
            '➡️': ['➡', '➡\N{VARIATION SELECTOR-15}'],
            '⬇️': ['⬇', '⬇\N{VARIATION SELECTOR-15}'],
            '⬅️': ['⬅', '⬅\N{VARIATION SELECTOR-15}'],
            '⬆️': ['⬆', '⬆\N{VARIATION SELECTOR-15}'],
            '🔙': ['🔚']
        }
        self.alternatives = {
            alt: can for can, alts in alternatives.items() for alt in alts
        }
        #print('ALTERNATIVES', self.alternatives)

        # TODO parse_entity()

    # clean

    async def close(self) -> None:
        """Close the database connection."""
        await self.redis.close()
        # Work around Redis not closing its connection pool (see
        # https://github.com/aio-libs/aioredis-py/issues/1103)
        try:
            await self.redis.connection_pool.disconnect() # type: ignore[misc]
        except CancelledError:
            pass
        await self.http.close()

    def get_mode(self, chat: str) -> Mode:
        """Get the current mode of *chat*."""
        return self._chat_modes.get(chat) or MainMode()

    def set_mode(self, chat: str, mode: Mode) -> None:
        """Set the current *mode* of *chat*."""
        if isinstance(mode, MainMode):
            self._chat_modes.pop(chat, None)
        else:
            self._chat_modes[chat] = mode

    def send(self, message: Message) -> None:
        """Send a *message*."""
        self._outbox.put_nowait(message)

    async def _handle_inbox(self, telegram: Telegram) -> None:
        logger = getLogger(__name__)
        logger.info('Started Telegram inbox')
        try:
            while True:
                try:
                    async for message in telegram.inbox():
                        reply = '⚠️ Oops, something went very wrong! We will fix the problem as soon as possible. Meanwhile, you may try again.'
                        with recovery():
                            reply = await shield(self.perform(message.chat, message.text))
                        self.send(Message(message.chat, reply))
                except ClientError as e:
                    logger.warning('Failed to receive Telegram messages (%s)', e)
                    await sleep(1)
        except CancelledError:
            logger.info('Stopped Telegram inbox')
            raise

    async def _handle_outbox(self, telegram: Telegram) -> None:
        logger = getLogger(__name__)
        logger.info('Started Telegram outbox')
        try:
            while True:
                message = await self._outbox.get()
                try:
                    with recovery():
                        while True:
                            try:
                                await telegram.send(message)
                                break
                            except ClientError as e:
                                logger.warning('Failed to send Telegram message (%s)', e)
                                await sleep(1)
                finally:
                    self._outbox.task_done()
        except CancelledError:
            logger.info('Stopped Telegram outbox')
            raise

    # /clean

    async def update(self) -> None:
        from inspect import iscoroutinefunction, signature
        for name, f in reversed(cast(dict[str, object], vars(updates)).items()):
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
        TICK = 60 * 60

        context.bot.set(self)

        self.time = int(datetime.now().timestamp() / TICK)
        await self.update()

        events_task = create_task(self._handle_events())
        inbox_task = None
        outbox_task = None
        if self.telegram:
            inbox_task = create_task(self._handle_inbox(self.telegram))
            outbox_task = create_task(self._handle_outbox(self.telegram))

        now = datetime.now().timestamp()
        now = now // TICK

        logger = getLogger(__name__)
        logger.info('Started bot')

        try:
            while True:
                with recovery():
                    space_ids = await cast(Awaitable[list[str]], self.redis.hvals('spaces_by_chat'))
                    for space_id in space_ids:
                        #space = Space(
                        #    await cast(Awaitable[dict[str, str]], self.redis.hgetall(f'Space:{space_id}')))
                        space = await self.get_space(space_id)
                        while space.time < self.time:
                            space = await space.tick(space.time)
                        create_task(space.tell_stories())

                            #print(
                            #    space.id, space.pet_name, space.time, 'M', space.meadow_vegetable_growth,
                            #    'W', space.woods_growth, 'F', space.pet_fur, 'N', space.pet_nutrition)
                            ##    [item.type for item in await space.get_objects()])

                logger.info('Simulated world at tick %d', self.time)

                await sleep((self.time + 1) * TICK - datetime.now().timestamp())
                self.time = int(datetime.now().timestamp() / TICK)

        except CancelledError:
            await cancel(events_task)
            if inbox_task:
                await cancel(inbox_task)
            if outbox_task:
                await cancel(outbox_task)
            logger.info('Stopped bot')
            raise

        #time = int(await cast('Awaitable[str | None]', self.redis.get('time')) or '0')
        #await self.redis.set('time', time) # type: ignore[misc]

    async def perform(self, chat: str, action: str) -> str:
        """TODO."""
        logger = getLogger(__name__)

        space_id = await self.redis.hget('spaces_by_chat', chat)
        if not space_id:
            space = await self.create_space(chat)
            create_task(space.tell_stories())
            logger.info('Created space for %s (%s)', chat, space.pet_name)
            return '🥚 You found an egg. 😮'

        space = await self.get_space(space_id)
        tokens = self._parse(action)
        tokens = [self.alternatives.get(token, token) for token in tokens]

        reply = await self.get_mode(chat).perform(space, *tokens)
        create_task(space.tell_stories())

        logger.info('%s (%s): %s', chat, space.pet_name, ' '.join(tokens))
        return reply

    async def get_space(self, id: str) -> Space:
        return Space(await self.redis.hgetall(id))

    async def get_furniture_item(self, furniture_id: str) -> Furniture:
        data = await self.redis.hgetall(furniture_id)
        return FURNITURE_TYPES[data['type']](data)

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
                'trail_supply': str(Space.TRAIL_SUPPLY_FULL),
                'pet_id': pet_id,
                'pet_name': 'Feini',
                'pet_is_egg': 'true',
                'pet_nutrition': str(Space.INTERVAL_S),
                'pet_fur': '0',
                'pet_activity_id': ''
            }
            pet_data = {
                'id': pet_id,
                'space_id': space_id,
                'dirt': str(Pet.MAX_DIRT - Space.INTERVAL_S),
                'clothing': ''
            }

            pipe.hset(space_id, mapping=data)
            blueprints = [
                '🪓', '✂️', '🍳', '🚿', '🧭', '🪃', '⚾', '🧸', '🛋️', '🪴', '⛲', '📺', '🗞️', '🎨']
            pipe.zadd(f'{space_id}.blueprints',
                      {blueprint: Space.BLUEPRINT_WEIGHTS[blueprint] for blueprint in blueprints})
            pipe.hset(pet_id, mapping=pet_data)

            stories = [
                {
                    'id': f'IntroStory:{randstr()}',
                    'space_id': space_id,
                    'chapter': 'start',
                    'update_time': str(self.time)
                }, {
                    'id': f'SewingStory:{randstr()}',
                    'space_id': space_id,
                    'chapter': 'scissors',
                    'update_time': str(self.time)
                }
            ]
            for story in stories:
                pipe.hset(story['id'], mapping=story)
                pipe.sadd(f'{space_id}.stories', story['id'])

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
        logger = getLogger(__name__)
        logger.info('Started event queue')

        try:
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
                with recovery():
                    event_type, space_id = event.split()
                    space = await self.get_space(space_id)
                    f = event_messages[event_type]
                    reply = await shield(f(space))
                    self.send(Message(space.chat, reply))
                    logger.info('%s (%s): %s', space.chat, space.pet_name, event_type)

        except CancelledError:
            logger.info('Stopped event queue')
            raise

# clean

@dataclass
class Message:
    """Chat message.

    .. attribute:: chat

       Related chat ID.

    .. attribute:: text

       Message content.
    """

    chat: str
    text: str

class Telegram:
    """Telegram messenger client.

    .. attribute:: key

       API key.
    """

    def __init__(self, key: str) -> None:
        self.key = key
        self._base = f'https://api.telegram.org/bot{self.key}/'

    async def inbox(self) -> AsyncIterator[Message]:
        """Message inbox.

        If there is a problem communicating with Telegram, a :exc:`aiohttp.ClientError` is raised.
        """
        # Note that if there is a crash while a batch of messages is yielded, the messages will be
        # repeated
        offset = 0
        while True:
            try:
                response = await context.bot.get().http.get(
                    urljoin(self._base, 'getUpdates'),
                    params={'offset': str(offset), 'timeout': '300'}, # type: ignore[misc]
                    timeout=320)
                await raise_for_status(response)
                loads = partial(cast(Callable[[], object], json.loads), object_hook=JSONObject)
                result = await cast(Awaitable[object], response.json(loads=loads))
            except JSONDecodeError as e:
                raise ClientPayloadError('Bad response format') from e
            except asyncio.TimeoutError as e:
                raise ClientError('Stalled request') from e

            try:
                if not isinstance(result, JSONObject):
                    raise ClientPayloadError(f'Bad result type {type(result).__name__}')
                for update in result.get('result', cls=list):
                    if not isinstance(update, JSONObject):
                        raise ClientPayloadError(f'Bad update type {type(update).__name__}')
                    update_id = update.get('update_id', cls=int)
                    if 'message' in update:
                        message = update.get('message', cls=JSONObject)
                        yield Message(str(message.get('chat', cls=JSONObject).get('id', cls=int)),
                                      message.get('text', cls=str))
                    offset = update_id + 1
            except TypeError as e:
                raise ClientPayloadError(str(e)) from e

    async def send(self, message: Message) -> None:
        """Send a *message*.

        If the indicated *chat* is not available, a :exc:`KeyError` is raised. If there is a problem
        communicating with the service, a :exc:`aiohttp.ClientError` is raised.
        """
        try:
            chat = int(message.chat)
        except ValueError:
            raise KeyError(message.chat) from None
        if not message.text.strip():
            return

        try:
            response = await context.bot.get().http.post(
                urljoin(self._base, 'sendMessage'),
                json={'chat_id': chat, 'text': message.text}) # type: ignore[misc]
            if response.status >= 500:
                await raise_for_status(response)
            loads = partial(cast(Callable[[], object], json.loads), object_hook=JSONObject)
            result = await cast(Awaitable[object], response.json(loads=loads))
        except JSONDecodeError as e:
            raise ClientPayloadError('Bad response format') from e
        except asyncio.TimeoutError as e:
            raise ClientError('Stalled request') from e

        if not response.ok:
            try:
                if not isinstance(result, JSONObject):
                    raise ClientPayloadError(f'Bad result type {type(result).__name__}')
                code = result.get('error_code', cls=int)
                if code in {400, 403}:
                    raise KeyError(message.chat)
                raise ClientPayloadError(f'Bad error_code {code}')
            except TypeError as e:
                raise ClientPayloadError(str(e)) from e

# /clean

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
