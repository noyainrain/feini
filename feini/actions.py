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

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from inspect import getmembers
import random
from random import randint
from textwrap import dedent
from typing import ClassVar, Generic, Protocol, TypeVar, cast, overload
import unicodedata

from . import context
from .items import Newspaper, Object, Palette, Plant, Television
from .space import Space
from .util import isemoji

_M = TypeVar('_M', bound='Mode', contravariant=True)

class _ActionCallable(Protocol[_M]):
    async def __call__(_, self: _M, space: Space, *args: str) -> str:
        # pylint: disable=no-self-argument
        pass

class _ActionMethod(Protocol):
    async def __call__(self, space: Space, *args: str) -> str:
        pass

class Action(Generic[_M]):
    """Perform a player action with the arguments *args* in *space*.

    A reaction message is returned.

    Actions are performed sequentially in a space, thus there are no race conditions.

    .. attribute:: func

       Annotated function.

    .. attribute:: name

       Name of the action.
    """

    def __init__(self, func: _ActionCallable[_M], name: str) -> None:
        self.func = func
        self.name = name

    @overload
    def __get__(self, instance: None, owner: type[_M] | None = None) -> Action[_M]:
        pass
    @overload
    def __get__(self, instance: _M, owner: type[_M] | None = None) -> _ActionMethod:
        pass
    def __get__(self, instance: _M | None,
                owner: type[_M] | None = None) -> Action[_M] | _ActionMethod:
        return self if instance is None else partial(self.func, instance)

def action(name: str) -> Callable[[_ActionCallable[_M]], Action[_M]]:
    """Decorator to define a player action called *name*."""
    return cast(Callable[[_ActionCallable[_M]], Action[_M]], partial(Action, name=name))

class Mode:
    """Chat mode comprising a set of player actions."""

    _actions: ClassVar[dict[str, Action[Mode]]]

    def __init__(self) -> None:
        if not hasattr(self, '_actions'):
            cls = type(self)
            def isaction(obj: object) -> bool:
                return isinstance(obj, Action)
            members = cast(list[tuple[str, Action[Mode]]], getmembers(cls, isaction))
            cls._actions = {member.name: member for _, member in members}

    async def perform(self, space: Space, *args: str) -> str:
        """Perform the action given by the arguments *args* in *space*.

        A reaction message is returned.
        """
        try:
            f = self._actions[args[0]].__get__(self)
        except (KeyError, IndexError):
            f = self.default
        return await f(space, *args)

    async def default(self, space: Space, *args: str) -> str:
        """Perform the default action if no other available action matches."""
        raise NotImplementedError()

class _EntityActionCallable(Protocol):
    async def __call__(_, self: MainMode, space: Space, entity: Object, *args: str) -> str:
        # pylint: disable=no-self-argument
        pass

def item_action(item: str) -> Callable[[_ActionCallable[MainMode]], Action[MainMode]]:
    """Decorator to define a player action with an *item*.

    If the player does not have such an item, an appropriate message is returned.
    """
    def decorator(func: _ActionCallable[MainMode]) -> Action[MainMode]:
        async def wrapper(self: MainMode, space: Space, *args: str) -> str:
            if not (item in space.resources or item in space.tools):
                return await self.default(space, *args)
            return await func(self, space, *args)
        return Action(wrapper, name=item)
    return decorator

def entity_action(entity_type: str) -> Callable[[_EntityActionCallable], Action[MainMode]]:
    """Decorator to define a player action with an *entity_type* entity.

    *entity* is the relevant entity. If there is no such entity, an appropriate message is returned.
    """
    def decorator(func: _EntityActionCallable) -> Action[MainMode]:
        async def wrapper(self: MainMode, space: Space, *args: str) -> str:
            entities = await space.get_objects()
            entity = next((entity for entity in entities if entity.type == entity_type), None)
            if not entity:
                return await self.default(space, *args)
            return await func(self, space, entity, *args)
        return Action(wrapper, name=entity_type)
    return decorator

class MainMode(Mode):
    """Main chat mode."""
    # pylint: disable=missing-docstring,no-self-use,unused-argument

    # /clean

    @action('⛺')
    async def view_tent(self, space: Space, *args: str) -> str:
        objects = [cast(str, getattr(item, 'state', item.type))
                   for item in await space.get_objects()]
        #items += ['⬜'] * (4 - len(items))
        #items = ['│'] + items + ['.'] + ['\u2003'] * (4 - len(items)) + ['│']
        items = ''.join(objects)
        resources = ''.join(space.resources or '-')
        tools = ''.join(space.tools)
        return f'⛺{items}\n\nResources:\n{resources}\nTools:\n{tools}'

    # clean

    async def view_resource(self, space: Space, *args: str) -> str:
        return random.choice([f'{args[0]} Good quality!', f'{args[0]} Beautiful!'])

    view_stone = item_action('🪨')(view_resource)
    view_wood = item_action('🪵')(view_resource)
    view_wool = item_action('🧶')(view_resource)

    @action('obtain')
    async def obtain(self, space: Space, *args: str) -> str:
        resources = args[1:] or ['_']
        try:
            await space.obtain(*resources)
        except ValueError as e:
            if 'debug' in str(e):
                return await self.default(space, *args)
            if 'resources' in str(e):
                return dedent(f"""\
                    obtain ⬜Resource ⬜…
                    Obtain some resources ({''.join(Space.RESOURCES)}).
                """)
            raise
        return 'You stocked up. 😅'

    # /clean

    @item_action('🧺')
    async def gather_meadow(self, space: Space, *args: str) -> str:
        resources = await space.gather_meadow()
        if resources:
            return f"🧺 You gathered {''.join(resources)} from the meadow. 😊"
        return '🧺 The meadow is empty. Maybe try again later?'

    @item_action('🪓')
    async def chop_wood(self, space: Space, *args: str) -> str:
        wood = await space.chop_wood()
        if wood:
            return f"🪓 You chopped {''.join(wood)} in the woods. 😊"
        return '🪓 There are no more logs in the woods. Maybe try again later?'

    @item_action('🔨')
    async def craft(self, space: Space, *args: str) -> str:
        try:
            typ = args[1]
        except IndexError:
            typ = '_'

        try:
            await space.craft(typ)
            return f'🔨 You crafted a new {typ}. 🥳'
        except ValueError as e:
            if 'typ' in str(e):
                tools = '\n'.join(f"{typ}: {''.join(cost)}"
                                  for typ, cost in list(space.COSTS.items())[:4])
                furniture = '\n'.join(f"{typ}: {''.join(cost)}"
                                      for typ, cost in list(space.COSTS.items())[4:])
                return f'🔨 ⬜Item\nCraft an item.\n\nTools:\n{tools}\nFurniture:\n{furniture}'
                #catalog = '\n'.join(
                #    f"{typ}: {''.join(cost)}" for typ, cost in bot.costs.items())
                #return f'🔨 ⬜Item\n\nCatalog:\n{catalog}'
            if 'resources' in str(e):
                return f"🔨 You need {''.join(space.COSTS[typ])} to craft a {typ}."
            raise

    # clean

    @entity_action('🪃')
    async def view_boomerang(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['🪃 Good quality!', '🪃 Beautiful!'])

    @entity_action('⚾')
    async def view_ball(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['⚾ Good quality!', '⚾ Beautiful!'])

    @entity_action('🧸')
    async def view_teddy(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['🧸 Good quality!', '🧸 Beautiful!'])

    @entity_action('🛋️')
    async def view_couch(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['🛋️ Good quality!', '🛋️ Beautiful!'])

    @entity_action('🪴')
    async def view_plant(self, space: Space, entity: Object, *args: str) -> str:
        assert isinstance(entity, Plant)
        return random.choice([f'{entity.state} Good quality!', f'{entity.state} Beautiful!'])

    @entity_action('⛲')
    async def view_fountain(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['⛲ Good quality!', '⛲ Beautiful!'])

    @entity_action('📺')
    async def view_television(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['📺 Good quality!', '📺 Beautiful!'])

    @entity_action('🗞️')
    async def view_newspaper(self, space: Space, entity: Object, *args: str) -> str:
        return random.choice(['🗞️ Good quality!', '🗞️ Beautiful!'])

    @entity_action('🎨')
    async def view_palette(self, space: Space, entity: Object, *args: str) -> str:
        assert isinstance(entity, Palette)
        return random.choice([f'{entity.state} Good quality!', f'{entity.state} Beautiful!'])

    # /clean

    @item_action('👋')
    async def touch(self, space: Space, *args: str) -> str:
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

    @item_action('🥕')
    async def feed_pet(self, space: Space, *args: str) -> str:
        try:
            await space.feed_pet()
            return f'🥕🐕 {space.pet_name} enjoys its veggies. 😊'
        except ValueError as e:
            #if 'resources' in str(e):
            #    return 'You do not have any 🥕 at the moment.'
            if 'pet_nutrition' in str(e):
                return f'🐕 {space.pet_name} seems full and ignores the 🥕.'
            raise

    @item_action('🧽')
    async def wash_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        try:
            await pet.wash()
        except ValueError:
            return pet_message(f'{space.pet_name} is clean and politely refuses.')
        return pet_message(f'{space.pet_name} waits patiently while you scrub it clean.', focus='🧽',
                           mood='😊')

    @item_action('✂️')
    async def shear_pet(self, space: Space, *args: str) -> str:
        wool = await space.use('✂️')
        if wool:
            return f"✂️ You gently cut {''.join(wool)} from {space.pet_name}. 😊"
        return f'✂️ {space.pet_name} seems reluctant. Maybe try again later?'

    @item_action('✏️')
    async def change_pet_name(self, space: Space, *args: str) -> str:
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

    async def default(self, space: Space, *args: str) -> str:
        word = args[0] if isemoji(args[0]) else f'“{args[0]}”'
        return f'You have no {word} at the moment. Maybe have a look in the tent ⛺?'

# Style guide: TODO. feelings described from oustide, e.g. looks hungry instead of is hungry. exceptions
# for simplicity for describing verbs, e.g. drawing passionetly or if it is a verb e.g. likes

def pet_message(text: str, *, focus: str = '', mood: str = '') -> str:
    """Compose a pet-related message containing *text*.

    TODO.
    """
    return f"{focus}🐕 {text} {mood}".strip()

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

@event_message('pet-hungry')
async def pet_hungry_message(space: Space) -> str:
    return pet_message(f'{space.pet_name} looks hungry. {say()}', focus='🍽️')

@event_message('pet-dirty')
async def pet_dirty_message(space: Space) -> str:
    return pet_message(f'{space.pet_name} is pretty dirty.', focus='💩')

@event_message('space-stroll-sponge')
async def space_stroll_sponge_message(space: Space) -> str:
    return pet_message(f'{space.pet_name} found a sponge at the stream.', focus='🧽', mood='😊')
