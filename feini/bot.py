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

from __future__ import annotations

import asyncio
from asyncio import CancelledError, Queue, create_task, shield, sleep
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import json
from json import JSONDecodeError
from inspect import iscoroutinefunction, signature
from logging import getLogger
from typing import Awaitable, AsyncIterator, Callable, cast
import unicodedata
from urllib.parse import urljoin

from aiohttp import ClientError, ClientPayloadError, ClientSession, ClientTimeout
import aioredis.client

from . import actions, context, updates
from .actions import MainMode, Mode
from .furniture import Furniture, FURNITURE_TYPES
from .space import Pet, Space
from .util import JSONObject, Redis, cancel, raise_for_status, randstr, recovery

class Bot:
    """Open Feini chatbot.

    .. attribute:: time

       Current time in ticks.

    .. attribute:: redis

       Redis database client.

    .. attribute:: http

       HTTP client.

    .. attribute:: telegram

       Telegram messenger client, if configured.

    .. attribute:: debug

       Indicates if debug mode is enabled.

    .. attribute:: TICK

       Duration of a tick in seconds.
    """

    TICK = 60 * 60

    def __init__(self, *, redis_url: str = 'redis:', telegram_key: str | None = None,
                 debug: bool = False) -> None:
        self.time = 0
        try:
            self.redis = cast(Redis,
                              aioredis.client.Redis.from_url(redis_url, decode_responses=True))
        except ValueError as e:
            raise ValueError(f'Bad redis_url {redis_url}') from e
        self.http = ClientSession(timeout=ClientTimeout(total=20))
        self.telegram = Telegram(telegram_key) if telegram_key else None
        self.debug = debug

        self._chat_modes: dict[str, Mode] = {}
        self._outbox: Queue[Message] = Queue()

    async def update(self) -> None:
        """Update the database."""
        def isupdate(obj: object) -> bool:
            return (iscoroutinefunction(obj) and
                    not signature(obj).parameters) # type: ignore[arg-type]
        # Use vars() instead of getmembers() to preserve order
        functions = [
            cast(Callable[[], Awaitable[None]], member)
            for member in cast(dict[str, object], vars(updates)).values() if isupdate(member)]
        for update in reversed(functions):
            await update()

    async def run(self) -> None:
        """Run the bot continuously."""
        context.bot.set(self)
        self.time = int(datetime.now().timestamp() / self.TICK)
        await self.update()

        events_task = create_task(self._handle_events())
        inbox_task = None
        outbox_task = None
        if self.telegram:
            inbox_task = create_task(self._handle_inbox(self.telegram))
            outbox_task = create_task(self._handle_outbox(self.telegram))

        logger = getLogger(__name__)
        logger.info('Started bot')

        try:
            while True:
                with recovery():
                    for space in await self.get_spaces():
                        for time in range(space.time, self.time):
                            await space.tick(time)
                        create_task(space.tell_stories())
                    logger.info('Simulated world at tick %d', self.time)
                await sleep((self.time + 1) * self.TICK - datetime.now().timestamp())
                self.time = int(datetime.now().timestamp() / self.TICK)

        except CancelledError:
            await cancel(events_task)
            if inbox_task:
                await cancel(inbox_task)
            if outbox_task:
                await cancel(outbox_task)
            logger.info('Stopped bot')
            raise

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

    async def perform(self, chat: str, action: str) -> str:
        """Perform an action for the given *chat*.

        The *action* string consists of arguments, where an argument is either an emoji or a word. A
        reaction message is returned.
        """
        logger = getLogger(__name__)
        try:
            space = await self.get_space_by_chat(chat)
        except KeyError:
            space = await self.create_space(chat)
            create_task(space.tell_stories())
            logger.info('Created space for %s (%s)', chat, space.pet_name)
            return '🥚 You found an egg. 😮'

        args = self._parse_action(action)
        reply = await self.get_mode(chat).perform(space, *args)
        create_task(space.tell_stories())
        logger.info('%s (%s): %s', chat, space.pet_name, ' '.join(args))
        return reply

    def get_mode(self, chat: str) -> Mode:
        """Get the current mode of *chat*."""
        return self._chat_modes.get(chat) or MainMode()

    def set_mode(self, chat: str, mode: Mode) -> None:
        """Set the current *mode* of *chat*."""
        if isinstance(mode, MainMode):
            self._chat_modes.pop(chat, None)
        else:
            self._chat_modes[chat] = mode

    async def get_spaces(self) -> set[Space]:
        """Get all spaces."""
        ids = await self.redis.hvals('spaces_by_chat')
        spaces = (await self.redis.hgetall(space_id) for space_id in ids)
        return {Space(data) async for data in spaces if data} # type: ignore[attr-defined,misc]

    async def get_space(self, space_id: str) -> Space:
        """Get the space given by *space_id*."""
        if not space_id.startswith('Space:'):
            raise ValueError(f'Bad space_id {space_id}')
        data = await self.redis.hgetall(space_id)
        if not data:
            raise KeyError(space_id)
        return Space(data)

    async def get_space_by_chat(self, chat: str) -> Space:
        """Get the space given by *chat*."""
        space_id = await self.redis.hget('spaces_by_chat', chat)
        if not space_id:
            raise KeyError(chat)
        return await self.get_space(space_id)

    async def get_pet(self, pet_id: str) -> Pet:
        """Get the pet given by *pet_id*."""
        if not pet_id.startswith('Pet:'):
            raise ValueError(f'Bad pet_id {pet_id}')
        data = await self.redis.hgetall(pet_id)
        if not data:
            raise KeyError(pet_id)
        return Pet(data)

    async def get_furniture_item(self, furniture_id: str) -> Furniture:
        """Get the furniture item given by *furniture_id*."""
        if not furniture_id.startswith('Object:'):
            raise ValueError(f'Bad furniture_id {furniture_id}')
        data = await self.redis.hgetall(furniture_id)
        if not data:
            raise KeyError(furniture_id)
        return FURNITURE_TYPES[data['type']](data)

    # TODO clean
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

    # TODO clean
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
                    self._send(Message(space.chat, reply))
                    logger.info('%s (%s): %s', space.chat, space.pet_name, event_type)

        except CancelledError:
            logger.info('Stopped event queue')
            raise

    async def _handle_inbox(self, telegram: Telegram) -> None:
        logger = getLogger(__name__)
        logger.info('Started Telegram inbox')
        try:
            while True:
                try:
                    async for message in telegram.inbox():
                        reply = ('⚠️ Oops, something went very wrong! We will fix the problem as '
                                 'soon as possible. Meanwhile, you may try again.')
                        with recovery():
                            reply = await shield(self.perform(message.chat, message.text))
                        self._send(Message(message.chat, reply))
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

    def _send(self, message: Message) -> None:
        self._outbox.put_nowait(message)

    # TODO clean
    def _parse_action(self, command: str) -> list[str]:
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
    #
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
