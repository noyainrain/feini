# pylint: disable=missing-docstring

from unittest import IsolatedAsyncioTestCase

from feini import context
from feini.bot import Bot
from feini.context import bot
from feini.items import Plant
from feini.space import Space

#class FeiniTestCase(IsolatedAsyncioTestCase):
#    async def asyncSetUp(self) -> None:
#        context.bot.set(Bot())

class FeiniTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.bot = Bot(debug=True)
        context.bot.set(self.bot)
        self.space = await self.bot.create_space('local')

    async def asyncTearDown(self) -> None:
        await self.bot.close()

    async def obtain(self, resources: list[str]) -> None:
        space = await self.bot.get_space(self.space.id)
        if '🪵'  in resources and '🪓' not in space.tools:
            await self.obtain(Space.COSTS['🪓'])
            await space.craft('🪓')
        if '🧶' in resources and '✂️' not in space.tools:
            await self.obtain(Space.COSTS['✂️'])
            await space.craft('✂️')

        resources = list(resources)
        while True:
            obtained = []
            if '🥕' in resources or '🪨' in resources:
                obtained += await space.gather_meadow()
            if '🪵' in resources:
                obtained += await space.chop_wood()
            if '🧶' in resources:
                obtained += await space.use('✂️')
            for resource in obtained:
                try:
                    resources.remove(resource)
                except ValueError:
                    pass
            if not resources:
                break
            space = await self.bot.get_space(self.space.id)
            await space.tick(space.time)

            #await self.space.gather_meadow()
            #space = await context.bot.get().get_space(self.space.id)
            #if space.resources.count('🥕') >= veggies:
            #    break
            #await space.tick(space.time)

class SpaceTest(FeiniTestCase):
    #bot: Bot
    #space: Space

    async def test_tick(self) -> None:
        space = self.space
        for _ in range(1000):
            await space.tick(space.time)
            space = await self.bot.get_space(self.space.id)
            if space.pet_activity_id != '':
                break
        else:
            self.fail()

    # clean

    async def test_obtain(self) -> None:
        await self.space.obtain('🪵', '🧶', '🥕')
        await self.space.obtain('🪵')
        space = await self.space.get()
        self.assertEqual(space.resources, ['🥕', '🪵', '🪵', '🧶']) # type: ignore[misc]

    # /clean

    async def test_feed_pet(self) -> None:
        await self.space.gather_meadow()
        await self.space.feed_pet()
        space = await bot.get().get_space(self.space.id)
        self.assertEqual(space.resources, ['🪨']) # type: ignore[misc]
        self.assertEqual(space.pet_nutrition, space.PET_NUTRITION_MAX)

    async def test_feed_pet_no_vegetable(self) -> None:
        with self.assertRaisesRegex(ValueError, 'resources'):
            await self.space.feed_pet()

    async def test_feed_pet_full(self) -> None:
        await self.space.gather_meadow()
        await self.space.feed_pet()
        with self.assertRaisesRegex(ValueError, 'pet_nutrition'):
            await self.space.feed_pet()

    async def test_gather_meadow(self) -> None:
        resources = await self.space.gather_meadow()
        space = await bot.get().get_space(self.space.id)
        self.assertEqual(resources, ['🥕', '🪨']) # type: ignore[misc]
        self.assertEqual(space.resources, resources)
        self.assertEqual(space.meadow_vegetable_growth, 0)

    async def test_gather_meadow_empty(self) -> None:
        await self.space.gather_meadow()
        resources = await self.space.gather_meadow()
        self.assertFalse(resources)

    async def test_chop_wood(self) -> None:
        await self.obtain(Space.COSTS['🪓'])
        await self.space.craft('🪓')
        wood = await self.space.chop_wood()
        space = await self.bot.get_space(self.space.id)
        self.assertEqual(wood, ['🪵']) # type: ignore[misc]
        self.assertEqual(space.resources, ['🥕', '🪵']) # type: ignore[misc]
        self.assertEqual(space.woods_growth, 0)

    # test_chop_woods empty

    async def test_use_scissors(self) -> None:
        await self.obtain(Space.COSTS['✂️'])
        await self.space.craft('✂️')
        wool = await self.space.use('✂️')
        space = await self.bot.get_space(self.space.id)
        self.assertEqual(wool, ['🧶']) # type: ignore[misc]
        self.assertEqual(space.resources, ['🥕', '🥕', '🥕', '🧶']) # type: ignore[misc]
        self.assertEqual(space.pet_fur, 0)

    async def test_use_scissors_no_pet_fur(self) -> None:
        await self.obtain(Space.COSTS['✂️'])
        await self.space.craft('✂️')
        await self.space.use('✂️')
        wool = await self.space.use('✂️')
        self.assertFalse(wool)

    async def test_craft(self) -> None:
        await self.obtain(Space.COSTS['🪓'])
        axe = await self.space.craft('🪓')
        space = await bot.get().get_space(self.space.id)
        self.assertEqual(axe, '🪓')
        self.assertEqual(space.tools, self.space.tools + ['🪓']) # type: ignore[misc]
        self.assertEqual(space.resources, ['🥕']) # type: ignore[misc]

    async def test_craft_home_item(self) -> None:
        await self.obtain(Space.COSTS['🪴'])
        plant = await self.space.craft('🪴')
        space = await bot.get().get_space(self.space.id)
        self.assertIsInstance(plant, Plant)
        self.assertEqual(await space.get_objects(), [plant]) # type: ignore[misc]
        self.assertEqual(space.resources, ['🥕', '🥕', '🥕']) # type: ignore[misc]

    async def test_craft_no_resources(self) -> None:
        with self.assertRaisesRegex(ValueError, 'resources'):
            await self.space.craft('🪴')

class PetTest(FeiniTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.pet = await self.space.get_pet()

    async def test_tick(self) -> None:
        await self.pet.tick()
        pet = await self.space.get_pet()
        self.assertEqual(pet.dirt, self.pet.dirt + 1)

    async def test_wash(self) -> None:
        await self.pet.wash()
        pet = await self.space.get_pet()
        self.assertFalse(pet.dirt)

    async def test_wash_clean(self) -> None:
        await self.pet.wash()
        with self.assertRaisesRegex(ValueError, 'dirt'):
            await self.pet.wash()
