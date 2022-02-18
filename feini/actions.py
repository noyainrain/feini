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

"""Player actions."""

# Style guide: TODO. feelings described from oustide, e.g. looks hungry instead of is hungry. exceptions
# for simplicity for describing verbs, e.g. drawing passionetly or if it is a verb e.g. likes

from __future__ import annotations

import random
from random import randint
from textwrap import dedent
from typing import Protocol
import unicodedata

from . import context
from .items import Newspaper, Object, Palette, Plant, Television
from .space import Space
from .util import isemoji

class Action(Protocol):
    async def __call__(self, space: Space, *args: str) -> str:
        """Perform a player action with the arguments *args* in *space*.

        A reaction message is returned.
        """

def pet_message(text: str, *, focus: str = '', mood: str = '') -> str:
    """Compose a pet-related message containing *text*.

    TODO."""
    return f"{focus}🐕 {text} {mood}".strip()

async def change_pet_name(space: Space, *args: str) -> str:
    if not (len(args) == 2 and not isemoji(args[1])):
        return dedent(f"""\
            ✏️ ⬜Name
            Change the name of {space.pet_name}.
        """)
    await space.change_pet_name(args[1])
    space = await space.get()
    return random.choice([
        pet_message(f'{space.pet_name} looks happy with its new name.', focus='✏️', mood='😊'),
        pet_message(f'{space.pet_name} approves its new name.', focus='✏️', mood='😊')
    ])

async def touch(space: Space, *args: str) -> str:
    await space.touch_pet()
    if space.pet_is_egg:
        return f'🥚 Crack! 🐕 {space.pet_name} hatched from the egg. It looks around curiously. 😊'
    if space.pet_nutrition == 0:
        return pet_message(f'{space.pet_name} looks hungry.', focus='🍽️')
    pet = await space.get_pet()
    if pet.dirt == pet.MAX_DIRT:
        return pet_message(f'{space.pet_name} is pretty dirty.', focus='💩')
    activity = await space.get_pet_activity()
    if activity == '':
        return pet_message(random.choice([f'{space.pet_name} wags its tail.', say(1)]))
    symbol = activity.type if isinstance(activity, Object) else activity
    f = context.bot.get().activities[symbol]
    return await f(space, activity)

async def view_tent(space: Space, *args: str) -> str:
    from typing import cast
    objects = [cast(str, getattr(item, 'state', item.type)) for item in await space.get_objects()]
    #items += ['⬜'] * (4 - len(items))
    #items = ['│'] + items + ['.'] + ['\u2003'] * (4 - len(items)) + ['│']
    items = ''.join(objects)
    resources = ''.join(space.resources or '-')
    tools = ''.join(space.tools)
    return f'⛺{items}\n\nResources:\n{resources}\nTools:\n{tools}'

async def gather_meadow(space: Space, *args: str) -> str:
    resources = await space.gather_meadow()
    if resources:
        return f"🧺 You gathered {''.join(resources)} from the meadow. 😊"
    return '🧺 The meadow is empty. Maybe try again later?'

async def chop_wood(space: Space, *args: str) -> str:
    wood = await space.chop_wood()
    if wood:
        return f"🪓 You chopped {''.join(wood)} in the woods. 😊"
    return f'🪓 There are no more logs in the woods. Maybe try again later?'

async def craft(space: Space, *args: str) -> str:
    bot = context.bot.get()
    try:
        typ = args[1]
    except IndexError as e:
        typ = '_'

    try:
        await space.craft(typ)
        return f'🔨 You crafted a new {typ}. 🥳'
    except ValueError as e:
        if 'typ' in str(e):
            tools = '\n'.join(f"{typ}: {''.join(cost)}" for typ, cost in list(bot.costs.items())[:4])
            furniture = '\n'.join(f"{typ}: {''.join(cost)}" for typ, cost in list(bot.costs.items())[4:])
            return f'🔨 ⬜Item\nCraft an item.\n\nTools:\n{tools}\nFurniture:\n{furniture}'
            #catalog = '\n'.join(
            #    f"{typ}: {''.join(cost)}" for typ, cost in bot.costs.items())
            #return f'🔨 ⬜Item\n\nCatalog:\n{catalog}'
        if 'resources' in str(e):
            return f"🔨 You need {''.join(bot.costs[typ])} to craft a {typ}."
        raise

async def feed_pet(space: Space, *args: str) -> str:
    try:
        await space.feed_pet()
        return f'🥕🐕 {space.pet_name} enjoys its veggies. 😊'
    except ValueError as e:
        #if 'resources' in str(e):
        #    return 'You do not have any 🥕 at the moment.'
        if 'pet_nutrition' in str(e):
            return f'🐕 {space.pet_name} seems full and ignores the 🥕.'
        raise

async def wash_pet(space: Space, *args: str) -> str:
    pet = await space.get_pet()
    try:
        await pet.wash()
    except ValueError:
        return pet_message(f'{space.pet_name} is clean and refuses.')
    return pet_message(f'{space.pet_name} waits patiently while you scrub it clean.', focus='🧽',
                       mood='😊')

async def shear_pet(space: Space, *args: str) -> str:
    wool = await space.use('✂️')
    if wool:
        return f"✂️ You gently cut {''.join(wool)} from {space.pet_name}. 😊"
    return f'✂️ {space.pet_name} seems reluctant. Maybe try again later?'

async def usage(space: Space, *args: str) -> str:
    # return f'🐕 {space.pet_name} seems confused.\n\n(Try 👋)'
    msg = random.choice(['Good quality!', 'Beautiful!'])
    return f'{args[0]} {msg}'

def say(n: int = 0) -> str:
    s = ' '.join([random.choice(['Woof!', 'Arf!']) for _ in range(randint(n, 2))])
    return s
    # return f'”{s}”' if s else ''

async def view_sleep(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, str)
    text = random.choice(
        [f'{space.pet_name} is taking a nap.', f'{space.pet_name} is snoring to itself.'])
    return pet_message(text, focus=activity)

async def view_leaves(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, str)
    return pet_message(f'{space.pet_name} is chasing after some leaves. {say()}', focus=activity)

async def view_boomerang(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    text = random.choice([
        f'{space.pet_name} is fetching the boomerang. {say()}',
        f'{space.pet_name} is throwing the boomerang far.'
    ])
    return pet_message(text, focus=activity.type)

async def view_ball(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(f'{space.pet_name} is playing with the ball. {say()}', focus=activity.type)

async def view_teddy(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(f'{space.pet_name} is cuddling with its teddy.', focus=activity.type)

async def view_couch(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(f'{space.pet_name} is relaxing on the couch.', focus=activity.type)

async def view_plant(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Plant)
    if activity.state == '🌺':
        text = f'{space.pet_name} is smelling the fresh blossoms.'
    else:
        text = f'{space.pet_name} is carefully watering the plant.'
    return pet_message(text, focus=activity.state)

async def view_fountain(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(f'{space.pet_name} is splashing around in the fountain. {say()}',
                       focus=activity.type) # 💦

async def view_television(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Television)
    return pet_message(f'{space.pet_name} seems hooked by {activity.show}.', focus=activity.type)

async def view_newspaper(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Newspaper)
    dot = '' if unicodedata.category(activity.article[-1]).startswith('P') else '.'
    return pet_message(f'{space.pet_name} is reading an article. {activity.article}{dot}',
                       focus=activity.type)

async def view_palette(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Palette)
    if activity.state == '🖼️':
        text = f'{space.pet_name} seems very content with its painting.'
    else:
        text = f'{space.pet_name} is painting something with passion.'
    return pet_message(text, focus=activity.state)

from collections.abc import Awaitable, Callable
from typing import overload
from functools import partial

#class listener:
#    def __init__(self, arg: ListenerFunction | ) -> None:
#        self.event_type = event_type
#        self.f = f
#
#    @overload
#    def __call__(self, space: Space, /) -> Awaitable[str]:
#        pass
#    @overload
#    def __call__(self, f: ListenerFunction, /) -> listener:
#        pass
#    def __call__(self, arg: Space | ListenerFunction, /) -> Awaitable[str] | listener:
#        if isinstance(arg, Space):
#            return self.f(arg)
#        else:
#            return listener(self.event_type, arg)

#class eventmessage:
#    @overload
#    def __new__(cls, f: Callable[[Space], Awaitable[str]], /) -> eventmessage:
#        pass
#    @overload
#    def __new__(cls, event_type: str, /) -> Callable[[Callable[[Space], Awaitable[str]]], eventmessage]:
#        pass
#    def __new__(cls, arg: Callable[[Space], Awaitable[str]] | str) -> eventmessage | Callable[[Callable[[Space], Awaitable[str]]], eventmessage]:
#        pass

# @subscriber('space-pet-is-hungry')
# @subscriber('space-update')

#from typing import TypeVar, Generic
#from types import FunctionType
#
#_T = TypeVar('_T')
#_C = TypeVar('_C', bound=Callable[[Space, str], object])
#
#class AnnotatedFunc(Generic[_C]):
#    __call__: _C
#
#    def __init__(self, f: _C) -> None:
#        self._f = f
#
#    def __call__(self, *args: object, **kwargs: object) -> object: # type: ignore[no-redef]
#        return self._f(*args, **kwargs) # type: ignore[misc]
#
#    @classmethod
#    def decorator(cls: _T) -> Callable[[_C], _T]:
#        pass
#
#class ActionFunc(AnnotatedFunc[Callable[[Space, str], Awaitable[str]]]):
#    def __init__(self, f: Callable[[Space, str], Awaitable[str]], *, action: str) -> None:
#        super().__init__(f)
#        self.action = action
#
#action = ActionFunc.decorator

class EventMessageFunc:
    """Write a message about an event in *space*.

    .. attribute:: func

       Wrapped function.

    .. attribute:: event_type

       Type of event the function handles.
    """

    def __init__(self, func: Callable[[Space], Awaitable[str]], event_type: str) -> None:
        self.func = func
        self.event_type = event_type

    async def __call__(self, space: Space) -> str:
        return await self.func(space)

def event_message(
    event_type: str
) -> Callable[[Callable[[Space], Awaitable[str]]], EventMessageFunc]:
    """Decorator to define an event message function that handles *event_type* events."""
    return partial(EventMessageFunc, event_type=event_type)

#from typing import ClassVar
#
#class EventMessageFunc:
#    event_type: ClassVar[str]
#
#    async def __call__(self, space: Space) -> str:
#        raise NotImplementedError()
#
#def eventmessage(
#    event_type: str
#) -> Callable[[Callable[[Space], Awaitable[str]]], EventMessageFunc]:
#    def wrap(f: Callable[[Space], Awaitable[str]]) -> EventMessageFunc:
#        class Sub(EventMessageFunc):
#            event_type = event_type
#
#            async def __call__(self, space: Space) -> str:
#                return await f(space)
#        return Sub()
#    return wrap

@event_message('pet-dirty')
async def pet_dirty_message(space: Space) -> str:
    return pet_message(f'{space.pet_name} is pretty dirty.', focus='💩')

@event_message('space-stroll-sponge')
async def space_stroll_sponge_message(space: Space) -> str:
    return pet_message(f'{space.pet_name} found a sponge at the stream.', focus='🧽', mood='😊')
