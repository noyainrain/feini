# TODO

"""TODO."""

from __future__ import annotations

from asyncio import get_event_loop, sleep, create_task
from contextlib import asynccontextmanager
from datetime import datetime
from logging import getLogger
import random
from typing import TypeVar, cast, Awaitable, AsyncIterator, Callable, overload, Literal
import unicodedata

from aioredis.exceptions import WatchError
from aiohttp import ClientSession, ClientError

from .actions import (
    touch, feed_pet, gather_meadow, craft, edit_pet_name, view_tent, chop_wood, shear_pet, usage,
    view_sleep, view_leaves, view_boomerang, view_ball, view_teddy, view_couch, view_plant,
    view_fountain, view_television, view_newspaper, view_palette, say)
from . import context
from .items import Newspaper, Object, Plant, Palette, Television
from .util import Redis, Pipeline, JSONObject, randstr

class Space:
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
        self.pet_name = data['pet_name']
        self.pet_is_egg = bool(data['pet_is_egg'])
        self.pet_nutrition = int(data['pet_nutrition'])
        self.pet_fur = int(data['pet_fur'])
        self.pet_activity_id = data['pet_activity_id']
        self.story = data['story']

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

    async def edit_pet_name(self, name: str) -> Space:
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
        self._commands: dict[str, Callable[[Space, str], Awaitable[str]]] = {
            '⛺': view_tent,
            '🧺': gather_meadow,
            '🪓': chop_wood,
            '🥕': feed_pet,
            '✂️': shear_pet,
            '🔨': craft,
            '✏️': edit_pet_name,
            '👋': touch
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

    async def run(self) -> None:
        print('STARTING BOT')
        context.bot.set(self)

        # get_event_loop().create_task(self._handle())
        create_task(self._handle())
        TICK = 60 * 60
        #TICK = 1
        #TICK = 30

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
            word = item if self.is_symbol(item) else f'“{item}”'
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
            data = {
                'id': f'Space:{randstr()}',
                'chat': chat,
                'time': str(self.time),
                'resources': '',
                'tools': '👋 ✏️ 🔨 🧺',
                'meadow_vegetable_growth': str(Space.MEADOW_VEGETABLE_GROWTH_MAX),
                'woods_growth': str(Space.WOODS_GROWTH_MAX),
                'pet_name': 'Feini',
                'pet_is_egg': 'true',
                'pet_nutrition': '0',
                'pet_fur': str(Space.PET_FUR_MAX),
                'pet_activity_id': '',
                'story': 'touch'
            }
            pipe.hset(data['id'], mapping=data)
            pipe.hset('spaces_by_chat', chat, data['id'])
            await pipe.execute()
            return Space(data)

    @staticmethod
    def is_symbol(string: str) -> bool:
        return unicodedata.category(string[0]) == 'So'

    def _parse(self, command: str) -> list[str]:
        if not command:
            return []
        category = unicodedata.category(command[0])
        if category[0] == 'Z': # space
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
        # TODO stop on whitespace also
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
