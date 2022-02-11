from unittest import IsolatedAsyncioTestCase

from feini.bot import Bot, Space, bot

class SpaceTest(IsolatedAsyncioTestCase):
    #bot: Bot
    #space: Space

    async def asyncSetUp(self) -> None:
        bot.set(Bot())
        self.space = await bot.get().create_space('local')

    async def test_feed_pet(self) -> None:
        await self.space.gather_meadow()
        await self.space.feed_pet()
        space = await bot.get().get_space(self.space.id)
        self.assertFalse(space.resources)
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
        self.assertEqual(resources, ['🥕']) # type: ignore[misc]
        self.assertEqual(space.resources, resources)
        self.assertEqual(space.meadow_vegetable_growth, 0)

    async def test_gather_meadow_empty(self) -> None:
        await self.space.gather_meadow()
        resources = await self.space.gather_meadow()
        self.assertFalse(resources)
