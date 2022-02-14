"""TODO."""

from __future__ import annotations

import random
from random import randint
import typing
import unicodedata

from . import context
from .items import Object, Newspaper, Palette, Plant, Television

if typing.TYPE_CHECKING:
    from .bot import Space

async def touch(space: Space, *args: str) -> str:
    await space.touch_pet()
    if space.pet_is_egg:
        return f'🥚 Crack! 🐕 {space.pet_name} hatched from the egg. It looks around curiously. 😊'
    activity = await space.get_pet_activity()
    if activity == '':
        return pet_message(space, '', random.choice([f'{space.pet_name} wags its tail.', say(1)]))
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
            return f'🔨 ⬜Item\n\nTools:\n{tools}\nFurniture:\n{furniture}'
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

async def shear_pet(space: Space, *args: str) -> str:
    wool = await space.use('✂️')
    if wool:
        return f"✂️ You gently cut {''.join(wool)} from {space.pet_name}. 😊"
    return f'✂️ {space.pet_name} seems reluctant. Maybe try again later?'

async def edit_pet_name(space: Space, *args: str) -> str:
    if len(args) < 2 or unicodedata.category(args[0][0]) == 'So':
        return f'✏️ ⬜Name'
    space = await space.edit_pet_name(args[1])
    return f'🐕 {space.pet_name} seems to like its new name. 😊'

async def usage(space: Space, *args: str) -> str:
    # return f'🐕 {space.pet_name} seems confused.\n\n(Try 👋)'
    msg = random.choice(['Good quality!', 'Beautiful!'])
    return f'{args[0]} {msg}'

def pet_message(space: Space, interest: str, text: str) -> str:
    mood_text = ''
    if space.pet_nutrition == 0:
        mood_text = f'🍽️ {space.pet_name} seems hungry.'
    return f'{interest}🐕 {text}\n\n{mood_text}'

def say(n: int = 0) -> str:
    s = ' '.join([random.choice(['Woof!', 'Arf!']) for _ in range(randint(n, 2))])
    return s
    # return f'”{s}”' if s else ''

async def view_sleep(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, str)
    text = random.choice(
        [f'{space.pet_name} is taking a nap.', f'{space.pet_name} is snoring to itself.'])
    return pet_message(space, activity, text)

async def view_leaves(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, str)
    return pet_message(space, activity, f'{space.pet_name} is chasing after some leaves. {say()}')

async def view_boomerang(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    text = random.choice([
        f'{space.pet_name} is fetching the boomerang. {say()}',
        f'{space.pet_name} is throwing the boomerang far.'
    ])
    return pet_message(space, activity.type, text)

async def view_ball(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(space, activity.type, f'{space.pet_name} is playing with the ball. {say()}')

async def view_teddy(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(space, activity.type, f'{space.pet_name} is cuddling with its teddy.')

async def view_couch(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(space, activity.type, f'{space.pet_name} is relaxing on the couch.')

async def view_plant(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Plant)
    if activity.state == '🌺':
        text = f'{space.pet_name} is smelling the fresh blossoms.'
    else:
        text = f'{space.pet_name} is carefully watering the plant.'
    return pet_message(space, activity.state, text)

async def view_fountain(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Object)
    return pet_message(space, activity.type,
                       f'{space.pet_name} is splashing around in the fountain. {say()}') # 💦

async def view_television(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Television)
    return pet_message(space, activity.type, f'{space.pet_name} seems hooked by {activity.show}.')

async def view_newspaper(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Newspaper)
    dot = '' if unicodedata.category(activity.article[-1]).startswith('P') else '.'
    return pet_message(space, activity.type,
                       f'{space.pet_name} is reading an article. {activity.article}{dot}')

async def view_palette(space: Space, activity: Object | str) -> str:
    assert isinstance(activity, Palette)
    if activity.state == '🖼️':
        text = f'{space.pet_name} seems very content with its painting.'
    else:
        text = f'{space.pet_name} is painting something with passion.'
    return pet_message(space, activity.state, text)
