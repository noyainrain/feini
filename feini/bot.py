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
from asyncio import CancelledError, Queue, Task, create_task, gather, shield, sleep
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from inspect import getmembers, iscoroutinefunction, signature
from itertools import takewhile
import json
from json import JSONDecodeError
from logging import getLogger
from typing import Awaitable, AsyncIterator, Callable, cast
import unicodedata
from urllib.parse import urljoin
from weakref import WeakSet

from aiohttp import ClientError, ClientPayloadError, ClientSession, ClientTimeout
import aioredis.client

import feini.space
from . import actions, context, updates
from .actions import EventMessageFunc, MainMode, Mode
from .furniture import DW, Furniture, TMDB, FURNITURE_TYPES
from .space import Event, Pet, Space
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

    .. attribute:: tmdb

       The Movie Database source.

    .. attribute:: dw

       Deutsche Welle source.

    .. attribute:: debug

       Indicates if debug mode is enabled.

    .. attribute:: TICK

       Duration of a tick in seconds.
    """

    TICK = 60 * 60

    def __init__(
        self, *, redis_url: str = 'redis:', telegram_key: str | None = None,
        tmdb_key: str | None = None, irc_url: str | None = None, debug: bool = False
    ) -> None:
        self.time = 0
        try:
            self.redis = cast(Redis,
                              aioredis.client.Redis.from_url(redis_url, decode_responses=True))
        except ValueError as e:
            raise ValueError(f'Bad redis_url {redis_url}') from e
        self.http = ClientSession(timeout=ClientTimeout(total=20))
        self.telegram = Telegram(telegram_key) if telegram_key else None
        self.tmdb = TMDB(key=tmdb_key)
        self.dw = DW()
        self.debug = debug

        self._chat_modes: dict[str, Mode] = {}
        self._story_tasks: WeakSet[Task[None]] = WeakSet()
        self._outbox: Queue[Message] = Queue()

        from . import messengers
        self.irc = messengers.IRC(irc_url) if irc_url else None

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

        from . import messengers
        assert self.irc
        await self.irc.connect([])
        async for message in self.irc.inbox():
            print('GOT MESSAGE', message)
            await self.irc.send(messengers.Message(message.chat, '🐕 Woof!'))

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
                        self._story_tasks.add(create_task(space.tell_stories()))
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
        await gather(*self._story_tasks) # type: ignore[misc]
        await self.redis.close()
        # Work around Redis not closing its connection pool (see
        # https://github.com/aio-libs/aioredis-py/issues/1103)
        try:
            await self.redis.connection_pool.disconnect() # type: ignore[misc]
        except CancelledError:
            pass
        await self.http.close()
        await self.tmdb.close()
        await self.dw.close()

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
            pet = await space.get_pet()
            self._story_tasks.add(create_task(space.tell_stories()))
            logger.info('Created space for %s (%s)', chat, pet.name)
            return '🥚 You found an egg. 😮'

        pet = await space.get_pet()
        args = self._parse_action(action)
        reply = await self.get_mode(chat).perform(space, *args)
        self._story_tasks.add(create_task(space.tell_stories()))
        logger.info('%s (%s): %s', chat, pet.name, ' '.join(args))
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

    async def events(self) -> AsyncIterator[Event]:
        """Stream of game events."""
        while True:
            _, data = await self.redis.blpop('events')
            name = data.split('␟', maxsplit=1)[0]
            cls = cast(object, getattr(feini.space, name))
            assert isinstance(cls, type) and issubclass(cls, Event) # type: ignore[misc]
            yield cast(type[Event], cls).parse(data)

    async def get_spaces(self) -> set[Space]:
        """Get all spaces."""
        ids = await self.redis.hvals('spaces_by_chat')
        return {Space(data) for space_id in ids if (data := await self.redis.hgetall(space_id))}

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

    async def create_space(self, chat: str) -> Space:
        """Create a new space for the given *chat*."""
        async with self.redis.pipeline() as pipe:
            await pipe.watch('spaces_by_chat')
            if await pipe.hexists('spaces_by_chat', chat):
                raise ValueError(f'Duplicate chat {chat}')

            pipe.multi()
            space_id = f'Space:{randstr()}'
            pet_id = f'Pet:{randstr()}'

            space = {
                'id': space_id,
                'chat': chat,
                'time': str(self.time),
                'resources': '',
                'tools': ' '.join(['👋', '✏️', '🔨', '🧺', '🧽']),
                'meadow_vegetable_growth': str(Space.MEADOW_VEGETABLE_GROWTH_MAX),
                'woods_growth': str(Space.WOODS_GROWTH_MAX),
                'trail_supply': str(Space.TRAIL_SUPPLY_MAX),
                'pet_id': pet_id
            }
            pipe.hset(space_id, mapping=space)
            pipe.hset('spaces_by_chat', chat, space_id)

            pet = {
                'id': pet_id,
                'space_id': space_id,
                'name': 'Feini',
                'hatched': '',
                'nutrition': str(8 - 1),
                'dirt': str(Pet.DIRT_MAX - (8 - 1)),
                'fur': '0',
                'clothing': '',
                'activity_id': ''
            }
            pipe.hset(pet_id, mapping=pet)

            blueprints = ['🪓', '✂️', '🍳', '🚿', '🧭', '🪃', '⚾', '🧸', '🛋️', '🪴', '⛲', '📺', '🗞️',
                          '🎨']
            pipe.zadd(f'{space_id}.blueprints',
                      {blueprint: Space.BLUEPRINT_WEIGHTS[blueprint] for blueprint in blueprints})

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

            await pipe.execute()
            return Space(space)

    async def _handle_events(self) -> None:
        def iseventmessagefunc(obj: object) -> bool:
            return isinstance(obj, EventMessageFunc)
        members = cast(list[tuple[str, EventMessageFunc]],
                       getmembers(actions, iseventmessagefunc))
        event_messages = {f.event_type: f for _, f in members}

        logger = getLogger(__name__)
        logger.info('Started event queue')
        try:
            async for event in self.events():
                with recovery():
                    space = await shield(event.get_space())
                    pet = await shield(space.get_pet())
                    reply = await shield(event_messages[event.type](event))
                    self._send(Message(space.chat, reply))
                    logger.info('%s (%s): %s', space.chat, pet.name, event.type)
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

    def _parse_action(self, action: str) -> list[str]:
        if not action:
            return []
        category = unicodedata.category(action[0])

        # Parse space
        if category.startswith('Z'):
            return self._parse_action(action[1:])

        # Parse emoji
        if category == 'So':
            variation_selectors = '\N{VARIATION SELECTOR-15}\N{VARIATION SELECTOR-16}'
            length = 2 if len(action) >= 2 and action[1] in variation_selectors else 1
            return [action[:length], *self._parse_action(action[length:])]

        # Parse word
        def isletter(character: str) -> bool:
            category = unicodedata.category(character)
            return not (category.startswith('Z') or category == 'So')
        word = ''.join(takewhile(isletter, action))
        return [word, *self._parse_action(action[len(word):])]

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
