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

# Message style guide: The pet is described from an outside perspective, e.g. "Feini looks happy" or
# "Feini is playing happily" instead of "Feini is excited".

# pylint: disable=missing-function-docstring,unused-argument

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from gettext import NullTranslations
from inspect import getmembers
import random
from random import randint
from textwrap import dedent
from typing import ClassVar, Generic, Protocol, TypeVar, cast, overload
import unicodedata

from . import context
from .furniture import Furniture, Houseplant, Newspaper, Palette, Television, FURNITURE_MATERIAL
from .space import Hike, Pet, Space, CHARACTER_NAMES
from .util import isemoji

ngettext = NullTranslations().ngettext

_M_contra = TypeVar('_M_contra', bound='Mode', contravariant=True)

class _ActionCallable(Protocol[_M_contra]):
    async def __call__(_, self: _M_contra, space: Space, *args: str) -> str:
        pass

class _ActionMethod(Protocol):
    async def __call__(self, space: Space, *args: str) -> str:
        pass

class Action(Generic[_M_contra]):
    """Perform a player action with the arguments *args* in *space*.

    A reaction message is returned.

    Actions are performed sequentially in a space, thus there are no race conditions.

    .. attribute:: func

       Annotated function.

    .. attribute:: name

       Name of the action.
    """

    def __init__(self, func: _ActionCallable[_M_contra], name: str) -> None:
        self.func = func
        self.name = name

    @overload
    def __get__(self, instance: None, owner: type[_M_contra] | None = None) -> Action[_M_contra]:
        pass
    @overload
    def __get__(self, instance: _M_contra, owner: type[_M_contra] | None = None) -> _ActionMethod:
        pass
    def __get__(self, instance: _M_contra | None,
                owner: type[_M_contra] | None = None) -> Action[_M_contra] | _ActionMethod:
        return self if instance is None else partial(self.func, instance)

def action(name: str) -> Callable[[_ActionCallable[_M_contra]], Action[_M_contra]]:
    """Decorator to define a player action called *name*."""
    return cast(Callable[[_ActionCallable[_M_contra]], Action[_M_contra]],
                partial(Action, name=name))

class Mode:
    """Chat mode comprising a set of player actions."""

    _actions: ClassVar[dict[str, Action[Mode]]]

    def __init__(self) -> None:
        if not hasattr(self, '_actions'):
            cls = type(self)
            def isaction(obj: object) -> bool:
                return isinstance(obj, Action)
            members = cast(list[tuple[str, Action[Mode]]], getmembers(cls, isaction))
            cls._actions = {action.name: action for _, action in members}

    async def perform(self, space: Space, *args: str) -> str:
        """Perform the action given by the arguments *args* in *space*.

        A reaction message is returned.
        """
        try:
            # pylint: disable=unnecessary-dunder-call
            f = self._actions[normalize_emoji(args[0])].__get__(self)
        except (KeyError, IndexError):
            f = self.default
        return await f(space, *args)

    async def default(self, space: Space, *args: str) -> str:
        """Perform the default action if no other available action matches."""
        raise NotImplementedError()

class _FurnitureActionCallable(Protocol):
    async def __call__(_, self: MainMode, space: Space, piece: Furniture, *args: str) -> str:
        pass

def item_action(item: str) -> Callable[[_ActionCallable[MainMode]], Action[MainMode]]:
    """Decorator to define a player action with an *item*.

    If the player does not have such an item, an appropriate message is returned.
    """
    def decorator(func: _ActionCallable[MainMode]) -> Action[MainMode]:
        async def wrapper(self: MainMode, space: Space, *args: str) -> str:
            if not (item in space.items or item in space.tools):
                return await self.default(space, *args)
            return await func(self, space, *args)
        return Action(wrapper, name=item)
    return decorator

def furniture_action(furniture_type: str) -> Callable[[_FurnitureActionCallable], Action[MainMode]]:
    """Decorator to define a player action with a *furniture_type* piece of furniture.

    *piece* is the relevant piece of furniture. If there is no such piece of furniture, an
    appropriate message is returned.
    """
    def decorator(func: _FurnitureActionCallable) -> Action[MainMode]:
        async def wrapper(self: MainMode, space: Space, *args: str) -> str:
            piece = next(
                (piece for piece in await space.get_furniture() if piece.type == furniture_type),
                None)
            if not piece:
                return await self.default(space, *args)
            return await func(self, space, piece, *args)
        return Action(wrapper, name=furniture_type)
    return decorator

class EventMessageFunc:
    """Write a message about an event in *space*.

    .. attribute:: func

       Annotated function.

    .. attribute:: event_type

       Type of event handled by the function.
    """

    def __init__(self, func: Callable[[Space], Awaitable[str]], event_type: str) -> None:
        self.func = func
        self.event_type = event_type

    async def __call__(self, space: Space) -> str:
        return await self.func(space)

def event_message(
    event_type: str
) -> Callable[[Callable[[Space], Awaitable[str]]], EventMessageFunc]:
    """Decorator to define an event message function about *event_type* events."""
    return partial(EventMessageFunc, event_type=event_type)

_EMOJI_VARIANTS = {
    '🪨': ['🧱'],
    '🧶': ['🧵', '🪢'],
    '🎧': ['🎧\N{VARIATION SELECTOR-15}', '🎧\N{VARIATION SELECTOR-16}'],
    '👓': ['👓\N{VARIATION SELECTOR-15}', '👓\N{VARIATION SELECTOR-16}'],
    '🕶️': ['🕶', '🕶\N{VARIATION SELECTOR-15}'],
    '👋': ['🤚', '🖐️', '🖐', '🖐\N{VARIATION SELECTOR-15}', '✋', '🖖'],
    '✏️': ['✏', '✏\N{VARIATION SELECTOR-15}', '✒️', '✒', '✒\N{VARIATION SELECTOR-15}', '🖋️', '🖋',
          '🖋\N{VARIATION SELECTOR-15}', '🖊️', '🖊', '🖊\N{VARIATION SELECTOR-15}'],
    '🧺': ['🪣'],
    '✂️': ['✂', '✂\N{VARIATION SELECTOR-15}'],
    '🔨': ['⚒️', '⚒', '⚒\N{VARIATION SELECTOR-15}', '🛠️', '🛠', '🛠\N{VARIATION SELECTOR-15}'],
    '🍳': ['🔪'],
    '🧽': ['🧴', '🧼'],
    '⚾': ['⚾\N{VARIATION SELECTOR-15}', '⚾\N{VARIATION SELECTOR-16}', '🥎'],
    '🛋️': ['🛋', '🛋\N{VARIATION SELECTOR-15}'],
    '⛲': ['⛲\N{VARIATION SELECTOR-15}', '⛲\N{VARIATION SELECTOR-16}'],
    '📺': ['📺\N{VARIATION SELECTOR-15}', '📺\N{VARIATION SELECTOR-16}'],
    '🗞️': ['🗞', '🗞\N{VARIATION SELECTOR-15}', '📰'],
    '🎨': ['🖌️', '🖌', '🖌\N{VARIATION SELECTOR-15}'],
    '⛺': ['⛺\N{VARIATION SELECTOR-15}', '⛺\N{VARIATION SELECTOR-16}', '🏕️', '🏕',
           '🏕\N{VARIATION SELECTOR-15}'],
    '➡️': ['➡', '➡\N{VARIATION SELECTOR-15}'],
    '⬇️': ['⬇', '⬇\N{VARIATION SELECTOR-15}'],
    '⬅️': ['⬅', '⬅\N{VARIATION SELECTOR-15}'],
    '⬆️': ['⬆', '⬆\N{VARIATION SELECTOR-15}'],
    '🔙': ['🔚'],
    '✴️': ['✴', '✴\N{VARIATION SELECTOR-15}'],
    '📍': ['📌']
}
_EMOJI_NORMAL_FORMS = {
    variant: emoji for emoji, variants in _EMOJI_VARIANTS.items() for variant in variants
}

def normalize_emoji(emoji: str) -> str:
    """Normalize the given *emoji*.

    A definite emoji is used for variants expressing the same concept. The most compact emoji
    presentation is used for variation sequences.
    """
    return _EMOJI_NORMAL_FORMS.get(emoji) or emoji

def speak() -> str:
    """Generate pet speech."""
    return ' '.join(random.choice(['Woof!', 'Arf!']) for _ in range(randint(1, 2)))

def pet_message(pet: Pet, text: str, *, focus: str = '', mood: str = '') -> str:
    """Write a message about *pet* containing *text*.

    *focus* is an optional emoji for something the pet is focused on. *mood* is an optional emoji
    conveying the mood of the message.
    """
    if focus and not isemoji(focus):
        raise ValueError(f'Bad focus {focus}')
    if mood and not isemoji(mood):
        raise ValueError(f'Bad mood {mood}')
    return f'{focus}{pet} {text} {mood}'.strip()

class MainMode(Mode):
    """Main chat mode."""

    _DIALOGUE = {
        'ghost-sewing-hello': ['Where am I?'],
        'ghost-sewing-daughter': [
            '(Ghost looks at a piece of cloth in their hands) The last thing I remember is sitting '
            'in my chair, making a scarf for my daughter. She always used to like those… I think…'
        ],
        'ghost-sewing-request': [
            'Dear, do you know where I could find {items} to finish this scarf?',
            'If I only had {items}, I could finish this scarf.'
        ],
        'ghost-sewing-blueprint': [
            '(You give {items} to Ghost) Thank you so much, dear! Please, let me return the favor '
            'and tell you a few things about sewing! (You get a sewing needle blueprint 📋)'
        ],
        'ghost-sewing-goodbye': [
            'Do you think she will forgive me? (Ghost slowly vanishes into thin air)'
        ]
    }

    @action('⛺')
    async def view_home(self, space: Space, *args: str) -> str:
        furniture = ''.join(str(piece) for piece in await space.get_furniture())
        characters = ''.join(character.avatar for character in await space.get_characters())
        return dedent(f"""\
            ⛺{furniture} {characters}

            Items:
            {''.join(space.items) or '-'}
            Tools:
            {''.join(space.tools)}
        """)

    async def _view_resource(self, space: Space, *args: str) -> str:
        resource = normalize_emoji(args[0])
        return random.choice([f'{resource} Good quality!', f'{resource} Beautiful!'])

    view_resource = item_action('🪨')(_view_resource)
    _view_wood = item_action('🪵')(_view_resource)
    _view_wool = item_action('🧶')(_view_resource)

    @action('obtain')
    async def obtain(self, space: Space, *args: str) -> str:
        items = [normalize_emoji(item) for item in args[1:]] or ['_']
        try:
            await space.obtain(*items)
        except ValueError as e:
            if 'debug' in str(e):
                return await self.default(space, *args)
            if 'items' in str(e):
                items = [item for items in Space.ITEM_CATEGORIES.values() for item in items]
                return dedent(f"""\
                    obtain ⬜Item ⬜…
                    Obtain some items ({''.join(items)}).
                """)
            raise
        return 'You stock up. 😅'

    @item_action('🧺')
    async def gather(self, space: Space, *args: str) -> str:
        resources = await space.gather()
        if not resources:
            return 'The meadow is empty. Maybe try again later?'
        return f"🧺 You gather {''.join(resources)} from the meadow. 😊"

    @item_action('🪓')
    async def chop_wood(self, space: Space, *args: str) -> str:
        wood = await space.chop_wood()
        if not wood:
            return 'There are no more logs in the woods. Maybe try again later?'
        return f"🪓 You chop {''.join(wood)} from the woods. 😊"

    @item_action('🔨')
    async def craft(self, space: Space, *args: str) -> str:
        try:
            blueprint = normalize_emoji(args[1])
        except IndexError:
            blueprint = ''
        material = ''.join((Space.TOOL_MATERIAL | FURNITURE_MATERIAL).get(blueprint) or '')

        try:
            await space.craft(blueprint)
            return f'🔨 You spend {material} to craft a new {blueprint}. 🥳'

        except ValueError as e:
            if 'blueprint' in str(e):
                blueprints = await space.get_blueprints()
                catalog = {
                    'Tools': {blueprint: cost for blueprint in blueprints
                              if (cost := Space.TOOL_MATERIAL.get(blueprint))},
                    'Furniture': {blueprint: cost for blueprint in blueprints
                                  if (cost := FURNITURE_MATERIAL.get(blueprint))}
                }
                line_break = '\n                    '
                catalog_blocks = {
                    category:
                        line_break.join(f"{blueprint}: {''.join(cost)}"
                                        for blueprint, cost in blueprints.items())
                        for category, blueprints in catalog.items()
                }
                catalog_text = line_break.join(f'{category}:{line_break}{block}'
                                               for category, block in catalog_blocks.items())
                return dedent(f"""\
                    🔨 ⬜Item
                    Craft a new item.

                    {catalog_text}
                """)

            if 'resources' in str(e):
                return f'You need {material} to craft a {blueprint}.'
            raise

    @item_action('🪡')
    async def sew(self, space: Space, *args: str) -> str:
        try:
            pattern = normalize_emoji(args[1])
        except IndexError:
            pattern = ''

        try:
            material = ''.join(space.CLOTHING_MATERIAL[pattern])
        except KeyError:
            clothes = '\n                '.join(
                f"{pattern}: {''.join(material)}"
                for pattern, material in Space.CLOTHING_MATERIAL.items())
            return dedent(f"""\
                🪡 ⬜Item
                Sew a new clothing item.

                Clothes:
                {clothes}
            """)

        try:
            await space.sew(pattern)
            return f'🪡 You spend {material} to sew a new {pattern}. 🥳'
        except ValueError as e:
            if 'resources' in str(e):
                return f'You need {material} to sew a {pattern}.'
            raise

    @item_action('🧭')
    async def hike(self, space: Space, *args: str) -> str:
        mode = HikeMode(await space.hike())
        context.bot.get().set_mode(space.chat, mode)
        return await mode.default(space)

    async def _try_hike(self, space: Space, *args: str) -> str:
        return 'You could use a compass 🧭 to hike.'

    try_hike = action('➡️')(_try_hike)
    _try_hike_move_south = action('⬇️')(_try_hike)
    _try_hike_move_west = action('⬅️')(_try_hike)
    _try_hike_move_north = action('⬆️')(_try_hike)
    _try_hike_stop = action('🔙')(_try_hike)
    _try_hike_green = action('🟩')(_try_hike)
    _try_hike_origin = action('✴️')(_try_hike)
    _try_hike_tree_a = action('🌲')(_try_hike)
    _try_hike_tree_b = action('🌳')(_try_hike)
    _try_hike_destination = action('📍')(_try_hike)

    @item_action('👋')
    async def touch_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        await pet.touch()

        if not space.pet_hatched:
            return (f'🥚 Crack! {space.pet_name} 🐕 hatched from the egg. It looks around '
                    'curiously. 😊')
        if space.pet_nutrition <= 0:
            return pet_message(pet, f'{space.pet_name} looks hungry.', focus='🍽️')
        if pet.dirt >= pet.DIRT_MAX:
            return pet_message(pet, f'{space.pet_name} is pretty dirty.', focus='💩')

        activity = await space.get_pet_activity()
        activity_type = activity.type if isinstance(activity, Furniture) else activity
        try:
            func = self._ACTIVITY_MESSAGES[activity_type]
        except KeyError:
            return random.choice([
                pet_message(pet, f'{space.pet_name} wags its tail.'), pet_message(pet, speak())])
        else:
            return await func(self, space, activity)

    @item_action('🥕')
    async def feed_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        try:
            await pet.feed()
        except ValueError as e:
            if 'pet_nutrition' in str(e):
                return pet_message(pet, f'{space.pet_name} seems full and ignores the veggies 🥕.')
            raise
        return random.choice([
            pet_message(pet, f'{space.pet_name} enjoys its veggies.', focus='🥕', mood='😊'),
            pet_message(pet, f'{space.pet_name} digs in.', focus='🥕', mood='😊')
        ])

    @item_action('🧽')
    async def wash_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        try:
            await pet.wash()
        except ValueError:
            return pet_message(pet, f'{space.pet_name} is clean and politely refuses.')
        return random.choice([
            pet_message(pet, f'{space.pet_name} waits patiently while you scrub it clean.',
                        focus='🧽', mood='😊'),
            pet_message(pet, f'You wash {space.pet_name} thoroughly.', focus='🧽', mood='😊')
        ])

    async def _dress_pet(self, space: Space, *args: str) -> str:
        clothing = normalize_emoji(args[0])
        pet = await space.get_pet()

        if pet.clothing == clothing:
            await pet.dress(None)
            pet = await space.get_pet()
            return pet_message(pet, f"{space.pet_name} lets you take off the {clothing}.",
                               mood='😊')

        await pet.dress(clothing)
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} looks very pretty.', mood='😊'),
            pet_message(pet, f'{space.pet_name} looks happy with its {clothing}.', mood='😊')
        ])

    dress_pet = item_action('🧢')(_dress_pet)
    _dress_pet_sun_hat = item_action('👒')(_dress_pet)
    _dress_pet_headphones = item_action('🎧')(_dress_pet)
    _dress_pet_glasses = item_action('👓')(_dress_pet)
    _dress_pet_sunglasses = item_action('🕶️')(_dress_pet)
    _dress_pet_goggles = item_action('🥽')(_dress_pet)
    _dress_pet_scarf = item_action('🧣')(_dress_pet)
    _dress_pet_ribbon = item_action('🎀')(_dress_pet)
    _dress_pet_ring = item_action('💍')(_dress_pet)

    @item_action('✂️')
    async def shear_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        wool = await pet.shear()
        if not wool:
            return pet_message(pet, f'{space.pet_name} is reluctant. Maybe try again later?')
        return pet_message(pet, f"You gently cut {''.join(wool)} from {space.pet_name}.",
                           focus='✂️', mood='😊')

    @item_action('✏️')
    async def change_name_of_pet(self, space: Space, *args: str) -> str:
        try:
            name = args[1]
        except IndexError:
            name = None
        if not name or isemoji(name):
            return dedent(f"""\
                ✏️ ⬜Name
                Change the name of {space.pet_name}.
            """)

        pet = await space.get_pet()
        await pet.change_name(name)
        space = await space.get()
        return random.choice([
            pet_message(pet, f'{space.pet_name} looks happy with its new name.', focus='✏️',
                        mood='😊'),
            pet_message(pet, f'{space.pet_name} approves its new name.', focus='✏️', mood='😊')
        ])

    @furniture_action('🪃')
    async def view_boomerang(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['🪃 Good quality!', '🪃 Beautiful!'])

    @furniture_action('⚾')
    async def view_ball(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['⚾ Good quality!', '⚾ Beautiful!'])

    @furniture_action('🧸')
    async def view_teddy(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['🧸 Good quality!', '🧸 Beautiful!'])

    @furniture_action('🛋️')
    async def view_couch(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['🛋️ Good quality!', '🛋️ Beautiful!'])

    @furniture_action('🪴')
    async def view_houseplant(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice([f'{piece} Good quality!', f'{piece} Beautiful!'])

    @furniture_action('⛲')
    async def view_fountain(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['⛲ Good quality!', '⛲ Beautiful!'])

    @furniture_action('📺')
    async def view_television(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['📺 Good quality!', '📺 Beautiful!'])

    @furniture_action('🗞️')
    async def view_newspaper(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice(['🗞️ Good quality!', '🗞️ Beautiful!'])

    @furniture_action('🎨')
    async def view_palette(self, space: Space, piece: Furniture, *args: str) -> str:
        return random.choice([f'{piece} Good quality!', f'{piece} Beautiful!'])

    @action('👻')
    async def talk_to_character(self, space: Space, *args: str) -> str:
        avatar = normalize_emoji(args[0])
        character = next(
            (character for character in await space.get_characters() if character.avatar == avatar),
            None)
        if not character:
            return f'{CHARACTER_NAMES[avatar]} {avatar} is not here at the moment.'

        message = await character.talk()
        text = random.choice(self._DIALOGUE[message.id])
        if message.taken:
            text = text.replace('{items}', ''.join(message.taken))
        elif message.request:
            text = text.replace('{items}', ''.join(message.request))
        return f'{avatar} {text}'

    async def default(self, space: Space, *args: str) -> str:
        word = normalize_emoji(args[0])
        if not isemoji(word):
            word = f'“{word}”'
        return f'You have no {word} at the moment. You can see your inventory in the tent ⛺.'

    async def _sleep_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, str)
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is taking a nap.', focus=activity),
            pet_message(pet, f'{space.pet_name} is snoring to itself.', focus=activity)
        ])

    async def _leaves_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, str)
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is chasing after some leaves. {speak()}',
                        focus=activity),
            pet_message(pet, f'{space.pet_name} is playing outdoors.', focus=activity)
        ])

    async def _boomerang_message(self, space: Space, activity: Furniture | str) -> str:
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is fetching the boomerang. {speak()}',
                        focus=str(activity)),
            pet_message(pet, f'{space.pet_name} is carrying the boomerang around.',
                        focus=str(activity))
        ])

    async def _ball_message(self, space: Space, activity: Furniture | str) -> str:
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is playing with the ball. {speak()}',
                        focus=str(activity)),
            pet_message(pet, f'{space.pet_name} is occupied with the ball.', focus=str(activity))
        ])

    async def _teddy_message(self, space: Space, activity: Furniture | str) -> str:
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is cuddling with its teddy.', focus=str(activity)),
            pet_message(pet, f'{space.pet_name} is guarding its teddy.', focus=str(activity))
        ])

    async def _couch_message(self, space: Space, activity: Furniture | str) -> str:
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is relaxing on the couch.', focus=str(activity)),
            pet_message(pet, f'{space.pet_name} is briefly resting its eyes.', focus=str(activity))
        ])

    async def _houseplant_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, Houseplant)
        pet = await space.get_pet()
        if activity.state == '🌺':
            text = f'{space.pet_name} is smelling the fresh blossoms.'
        else:
            text = f'{space.pet_name} is carefully watering the houseplant.'
        return pet_message(pet, text, focus=str(activity))

    async def _fountain_message(self, space: Space, activity: Furniture | str) -> str:
        pet = await space.get_pet()
        return random.choice([
            pet_message(pet, f'{space.pet_name} is splashing around in the fountain. {speak()}',
                        focus=str(activity)),
            pet_message(pet, f'{space.pet_name} is dipping its toes in the water.',
                        focus=str(activity))
        ])

    async def _television_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, Television)
        pet = await space.get_pet()
        return pet_message(pet, f'{space.pet_name} is hooked by {activity.show}.',
                           focus=str(activity))

    async def _newspaper_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, Newspaper)
        pet = await space.get_pet()
        period = '' if unicodedata.category(activity.article[-1]).startswith('P') else '.'
        return pet_message(
            pet, f'{space.pet_name} is reading an article. {activity.article}{period}',
            focus=str(activity))

    async def _palette_message(self, space: Space, activity: Furniture | str) -> str:
        assert isinstance(activity, Palette)
        pet = await space.get_pet()
        if activity.state == '🖼️':
            text = f'{space.pet_name} looks very content with its painting.'
        else:
            text = f'{space.pet_name} is painting something with passion.'
        return pet_message(pet, text, focus=str(activity))

    _ACTIVITY_MESSAGES: dict[str, Callable[[MainMode, Space, Furniture | str], Awaitable[str]]] = {
        '💤': _sleep_message,
        '🍃': _leaves_message,
        '🪃': _boomerang_message,
        '⚾': _ball_message,
        '🧸': _teddy_message,
        '🛋️': _couch_message,
        '🪴': _houseplant_message,
        '⛲': _fountain_message,
        '📺': _television_message,
        '🗞️': _newspaper_message,
        '🎨': _palette_message
    }

class HikeMode(Mode):
    """Hike minigame chat mode.

    .. attribute:: hike

       Active hike.
    """

    # pylint: disable=unused-argument

    def __init__(self, hike: Hike) -> None:
        super().__init__()
        self.hike = hike

    async def _move(self, space: Space, *args: str) -> str:
        try:
            move = await self.hike.move([normalize_emoji(direction) for direction in args])
        except ValueError as e:
            if 'directions' in str(e):
                return await self.default(space)
            raise

        pet = await space.get_pet()
        emoji = ''.join(item for step in move for item in step)

        end = move[-1][1]
        parts = []
        if end in Hike.GROUND:
            parts.append(
                random.choice([
                    "Apparently that wasn't the right way. 😵‍💫",
                    "You missed a turn somewhere. 😵‍💫"
                ]))
        elif end in Hike.TREES:
            parts.append(
                random.choice([
                    f'{space.pet_name} was blocked by a tree.',
                    f'{space.pet_name} got stuck in the thicket.'
                ]))
        elif end == '📍':
            moves = len(self.hike.moves)
            parts.append(
                ngettext(
                    'You finished the hike in 1 move. 🥳',
                    'You finished the hike in {moves} moves. 🥳', moves
                ).format(moves=moves))
        else:
            assert False
        if any(tile == self.hike.resource for _, tile in move):
            parts.append(
                random.choice([
                    f'{space.pet_name} found a {self.hike.resource}. 😊',
                    f'{space.pet_name} fetched a {self.hike.resource} en route. 😊'
                ]))

        trail = ''
        if self.hike.finished:
            context.bot.get().set_mode(space.chat, MainMode())
            trail = f'\n\n{self.hike}'

        return f"{pet}{emoji} {' '.join(parts)}{trail}"

    move = action('➡️')(_move)
    _move_south = action('⬇️')(_move)
    _move_west = action('⬅️')(_move)
    _move_north = action('⬆️')(_move)

    @action('🔙')
    async def stop(self, space: Space, *args: str) -> str:
        context.bot.get().set_mode(space.chat, MainMode())
        pet = await space.get_pet()
        moves = len(self.hike.moves)
        text = ngettext(
            'You return home after 1 move.', 'You return home after {moves} moves.', moves
        ).format(moves=moves)
        return f'{pet} {text}\n\n{self.hike}'

    async def default(self, space: Space, *args: str) -> str:
        return dedent("""\
            🧭 Hike: Navigate the trail and find your destination 📍.

            ⬆️➡️⬇️⬅️: Move four steps in the given direction, e.g. ⬅️⬆️⬆️⬅️. Every move starts from the same spot.
            🔙: Return home.
        """)

@event_message('pet-hungry')
async def pet_hungry_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} looks hungry. {speak()}', focus='🍽️')

@event_message('pet-dirty')
async def pet_dirty_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is pretty dirty.', focus='💩')

@event_message('space-explain-touch')
async def space_explain_touch_message(space: Space) -> str:
    return 'ℹ️ You can touch the egg by sending a 👋 emoji. What will happen?'

@event_message('space-explain-gather')
async def space_explain_gather_message(space: Space) -> str:
    return f'ℹ️ {space.pet_name} looks hungry. You can gather some veggies with 🧺.'

@event_message('space-explain-feed')
async def space_explain_feed_message(space: Space) -> str:
    return f'ℹ️ You can now feed {space.pet_name} with 🥕.'

@event_message('space-explain-craft')
async def space_explain_craft_message(space: Space) -> str:
    return (f'ℹ️ You can craft tools and furniture for {space.pet_name} with 🔨. You can currently '
            'afford to craft an axe with 🔨🪓.')

@event_message('space-explain-basics')
async def space_explain_basics_message(space: Space) -> str:
    return ('ℹ️ All items are placed in the tent. You can view it with ⛺. You can watch and pet '
            f'{space.pet_name} any time with 👋.')

@event_message('space-visit-ghost')
async def space_visit_ghost_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} has seen a ghost. {speak()}', focus='👻', mood='😮')

@event_message('space-stroll-compass-blueprint')
async def space_stroll_compass_blueprint_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} was digging and found a compass blueprint.',
                       focus='📋', mood='😊')

@event_message('space-stroll-sponge')
async def space_stroll_sponge_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} found a sponge at the stream.', focus='🧽',
                       mood='😊')
