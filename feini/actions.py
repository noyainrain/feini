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

# pylint: disable=missing-function-docstring

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
from .furniture import Furniture, Houseplant, Newspaper, Palette, Television, FURNITURE_TYPES
from .space import Hike, Pet, Space, CHARACTER_NAMES
from .util import isemoji

_M = TypeVar('_M', bound='Mode', contravariant=True)

ngettext = NullTranslations().ngettext

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
            cls._actions = {action.name: action for _, action in members}

    async def perform(self, space: Space, *args: str) -> str:
        """Perform the action given by the arguments *args* in *space*.

        A reaction message is returned.
        """
        try:
            f = self._actions[normalize_emoji(args[0])].__get__(self)
        except (KeyError, IndexError):
            f = self.default
        return await f(space, *args)

    async def default(self, space: Space, *args: str) -> str:
        """Perform the default action if no other available action matches."""
        raise NotImplementedError()

class _EntityActionCallable(Protocol):
    async def __call__(_, self: MainMode, space: Space, entity: Furniture, *args: str) -> str:
        # pylint: disable=no-self-argument
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

# TODO in actions.py: (use on first action arg and match with actions, so maybe in Mode)
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
    """TODO. emoji variations, multiple emojis expressing the same concept and text alias.
    normalize. *emoji* may also be a text representation"""
    return _EMOJI_NORMAL_FORMS.get(emoji) or emoji

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

    # pylint: disable=no-self-use,unused-argument

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
        furniture = ''.join(str(item) for item in await space.get_objects())
        characters = ''.join(character.avatar for character in await space.get_characters())
        return dedent(f"""\
            ⛺{furniture} {characters}

            Items:
            {''.join(space.resources) or '-'}
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

    # clean

    @item_action('🔨')
    async def craft(self, space: Space, *args: str) -> str:
        try:
            blueprint = normalize_emoji(args[1])
        except IndexError:
            blueprint = '_'

        try:
            await space.craft(blueprint)
            return f"🔨 You spent {''.join(Space.COSTS[blueprint])} to craft a new {blueprint}. 🥳"

        except ValueError as e:
            if 'blueprint' in str(e):
                blueprints = await space.get_blueprints()
                catalog = {
                    'Tools': [
                        blueprint for blueprint in blueprints
                        if blueprint in space.ITEM_CATEGORIES['tool']],
                    'Furniture': [blueprint
                                  for blueprint in blueprints if blueprint in FURNITURE_TYPES]
                }
                line_break = '\n                    '
                catalog_material = {
                    category:
                        line_break.join(f"{blueprint}: {''.join(space.COSTS[blueprint])}"
                                        for blueprint in blueprints)
                        for category, blueprints in catalog.items()
                }
                catalog_text = line_break.join(f'{category}:{line_break}{blueprints}'
                                               for category, blueprints in catalog_material.items())
                return dedent(f"""\
                    🔨 ⬜Item
                    Craft a new item.

                    {catalog_text}
                """)

            if 'resources' in str(e):
                return f"You need {''.join(Space.COSTS[blueprint])} to craft a {blueprint}."
            raise

    @item_action('🪡')
    async def sew(self, space: Space, *args: str) -> str:
        try:
            pattern = normalize_emoji(args[1])
        except IndexError:
            pattern = '_'

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
            return f'🪡 You spent {material} to sew a new {pattern}. 🥳'
        except ValueError as e:
            if 'resources' in str(e):
                return f'You need {material} to sew a {pattern}.'
            raise

    async def _dress_pet(self, space: Space, *args: str) -> str:
        clothing = normalize_emoji(args[0])
        pet = await space.get_pet()

        if pet.clothing == clothing:
            await pet.dress(None)
            return pet_message(await space.get_pet(),
                               f"{space.pet_name} let's you take off the {clothing}.", mood='😊')

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

    @entity_action('🪃')
    async def view_boomerang(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['🪃 Good quality!', '🪃 Beautiful!'])

    @entity_action('⚾')
    async def view_ball(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['⚾ Good quality!', '⚾ Beautiful!'])

    @entity_action('🧸')
    async def view_teddy(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['🧸 Good quality!', '🧸 Beautiful!'])

    @entity_action('🛋️')
    async def view_couch(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['🛋️ Good quality!', '🛋️ Beautiful!'])

    @entity_action('🪴')
    async def view_plant(self, space: Space, entity: Furniture, *args: str) -> str:
        assert isinstance(entity, HousePlant)
        return random.choice([f'{entity.state} Good quality!', f'{entity.state} Beautiful!'])

    @entity_action('⛲')
    async def view_fountain(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['⛲ Good quality!', '⛲ Beautiful!'])

    @entity_action('📺')
    async def view_television(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['📺 Good quality!', '📺 Beautiful!'])

    @entity_action('🗞️')
    async def view_newspaper(self, space: Space, entity: Furniture, *args: str) -> str:
        return random.choice(['🗞️ Good quality!', '🗞️ Beautiful!'])

    @entity_action('🎨')
    async def view_palette(self, space: Space, entity: Furniture, *args: str) -> str:
        assert isinstance(entity, Palette)
        return random.choice([f'{entity.state} Good quality!', f'{entity.state} Beautiful!'])

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

    # /clean

    @item_action('👋')
    async def touch(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        await space.touch_pet()
        if space.pet_hatched:
            return f'🥚 Crack! 🐕 {space.pet_name} hatched from the egg. It looks around curiously. 😊'
        if space.pet_nutrition == 0:
            return pet_message(pet, f'{space.pet_name} looks hungry.', focus='🍽️')
        pet = await space.get_pet()
        if pet.dirt == pet.DIRT_MAX:
            return pet_message(pet, f'{space.pet_name} is pretty dirty.', focus='💩')
        activity = await space.get_pet_activity()
        if activity == '':
            return pet_message(pet, random.choice([f'{space.pet_name} wags its tail.', say(1)]))
        symbol = activity.type if isinstance(activity, Furniture) else activity
        # f = context.bot.get().activities[symbol]
        f = _ACTIVITY_MESSAGES[symbol]
        return await f(space, activity)

    @item_action('🥕')
    async def feed_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        try:
            await space.feed_pet()
            return pet_message(pet, f'{space.pet_name} enjoys its veggies.', focus='🥕', mood='😊')
        except ValueError as e:
            #if 'resources' in str(e):
            #    return 'You do not have any 🥕 at the moment.'
            if 'pet_nutrition' in str(e):
                return pet_message(pet, f'{space.pet_name} seems full and ignores the 🥕.')
            raise

    @item_action('🧽')
    async def wash_pet(self, space: Space, *args: str) -> str:
        pet = await space.get_pet()
        try:
            await pet.wash()
        except ValueError:
            return pet_message(pet, f'{space.pet_name} is clean and politely refuses.')
        return pet_message(pet, f'{space.pet_name} waits patiently while you scrub it clean.',
                           focus='🧽', mood='😊')

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
        pet = await space.get_pet()
        await space.change_pet_name(args[1])
        space = await space.get()
        return random.choice([
            pet_message(pet, f'{space.pet_name} looks happy with its new name.', focus='✏️', mood='😊'),
            pet_message(pet, f'{space.pet_name} approves its new name.', focus='✏️', mood='😊')
        ])

    async def default(self, space: Space, *args: str) -> str:
        word = normalize_emoji(args[0]) if isemoji(args[0]) else f'“{args[0]}”'
        return f'You have no {word} at the moment. Maybe have a look in the tent ⛺?'

# clean

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
        if any(field == self.hike.resource for _, field in move):
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
            'You returned home after 1 move.', 'You returned home after {moves} moves.', moves
        ).format(moves=moves)
        return f'{pet} {text}\n\n{self.hike}'

    async def default(self, space: Space, *args: str) -> str:
        return dedent("""\
            🧭 Hike: Navigate the trail and find your destination 📍.

            ⬆️➡️⬇️⬅️: Move four steps in the given direction, e.g. ⬅️⬆️⬆️⬅️. Every move starts from the same spot.
            🔙: Return home.
        """)

# /clean

# Style guide: TODO. feelings described from oustide, e.g. looks hungry instead of is hungry. exceptions
# for simplicity for describing verbs, e.g. drawing passionetly or if it is a verb e.g. likes

def say(n: int = 0) -> str:
    s = ' '.join([random.choice(['Woof!', 'Arf!']) for _ in range(randint(n, 2))])
    return s
    # return f'”{s}”' if s else ''

async def view_sleep(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, str)
    pet = await space.get_pet()
    text = random.choice(
        [f'{space.pet_name} is taking a nap.', f'{space.pet_name} is snoring to itself.'])
    return pet_message(pet, text, focus=activity)

async def view_leaves(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, str)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is chasing after some leaves. {say()}',
                       focus=activity)

async def view_boomerang(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Furniture)
    pet = await space.get_pet()
    text = random.choice([
        f'{space.pet_name} is fetching the boomerang. {say()}',
        f'{space.pet_name} is throwing the boomerang far.'
    ])
    return pet_message(pet, text, focus=activity.type)

async def view_ball(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Furniture)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is playing with the ball. {say()}',
                       focus=activity.type)

async def view_teddy(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Furniture)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is cuddling with its teddy.', focus=activity.type)

async def view_couch(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Furniture)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is relaxing on the couch.', focus=activity.type)

async def view_plant(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, HousePlant)
    pet = await space.get_pet()
    if activity.state == '🌺':
        text = f'{space.pet_name} is smelling the fresh blossoms.'
    else:
        text = f'{space.pet_name} is carefully watering the plant.'
    return pet_message(pet, text, focus=activity.state)

async def view_fountain(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Furniture)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is splashing around in the fountain. {say()}',
                       focus=activity.type) # 💦

async def view_television(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Television)
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} seems hooked by {activity.show}.',
                       focus=activity.type)

async def view_newspaper(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Newspaper)
    pet = await space.get_pet()
    dot = '' if unicodedata.category(activity.article[-1]).startswith('P') else '.'
    return pet_message(pet, f'{space.pet_name} is reading an article. {activity.article}{dot}',
                       focus=activity.type)

async def view_palette(space: Space, activity: Furniture | str) -> str:
    assert isinstance(activity, Palette)
    pet = await space.get_pet()
    if activity.state == '🖼️':
        text = f'{space.pet_name} seems very content with its painting.'
    else:
        text = f'{space.pet_name} is painting something with passion.'
    return pet_message(pet, text, focus=activity.state)

#self.activities: dict[str, Callable[[Space, Object | str], Awaitable[str]]] = {
#self.activities = {
_ACTIVITY_MESSAGES: dict[str, Callable[[Space, Furniture | str], Awaitable[str]]] = {
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
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} looks hungry. {say()}', focus='🍽️')

@event_message('pet-dirty')
async def pet_dirty_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} is pretty dirty.', focus='💩')

# clean

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
    return pet_message(pet, f'{space.pet_name} has seen a ghost. {say()}', focus='👻', mood='😮')

# /clean

@event_message('space-stroll-compass-blueprint')
async def space_stroll_compass_blueprint_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} was digging and found a compass blueprint.', focus='📋',
                       mood='😊')

@event_message('space-stroll-sponge')
async def space_stroll_sponge_message(space: Space) -> str:
    pet = await space.get_pet()
    return pet_message(pet, f'{space.pet_name} found a sponge at the stream.', focus='🧽', mood='😊')
