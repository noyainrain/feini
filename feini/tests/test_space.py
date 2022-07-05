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

# pylint: disable=missing-docstring

# /clean

from itertools import cycle, islice

from feini.context import bot
from feini.furniture import Houseplant, FURNITURE_MATERIAL
from feini.space import Hike, Pet, Space
from .test_bot import TestCase

# clean

class SpaceTest(TestCase):
    async def test_tick(self) -> None:
        await self.space.tick(self.space.time)
        space = await self.space.get()
        self.assertEqual(space.trail_supply, Space.TRAIL_SUPPLY_MAX + 1)

        for _ in range(1000):
            if space.pet_activity_id != '':
                break
            await space.tick(space.time)
            space = await space.get()
        else:
            self.fail()

    async def test_obtain(self) -> None:
        await self.space.obtain('🪵', '🧶', '🥕')
        await self.space.obtain('🪵')
        space = await self.space.get()
        self.assertEqual(space.items, ['🥕', '🪵', '🪵', '🧶']) # type: ignore[misc]

    # /clean

    async def test_feed_pet(self) -> None:
        await self.space.gather_meadow()
        await self.space.feed_pet()
        space = await bot.get().get_space(self.space.id)
        self.assertEqual(space.items, ['🪨']) # type: ignore[misc]
        self.assertEqual(space.pet_nutrition, Pet.NUTRITION_MAX)

    async def test_feed_pet_no_vegetable(self) -> None:
        with self.assertRaisesRegex(ValueError, 'items'):
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
        self.assertEqual(space.items, resources)
        self.assertEqual(space.meadow_vegetable_growth, 0)

    async def test_gather_meadow_empty(self) -> None:
        await self.space.gather_meadow()
        resources = await self.space.gather_meadow()
        self.assertFalse(resources)

    async def test_chop_wood(self) -> None:
        await self.space.obtain(*Space.TOOL_MATERIAL['🪓'])
        await self.space.craft('🪓')
        wood = await self.space.chop_wood()
        space = await self.bot.get_space(self.space.id)
        self.assertEqual(wood, ['🪵']) # type: ignore[misc]
        self.assertEqual(space.items, ['🪵']) # type: ignore[misc]
        self.assertEqual(space.woods_growth, 0)

    # test_chop_woods empty

    # clean

    async def test_use_scissors(self) -> None:
        await self.space.obtain('✂️')
        for tick in range(Pet.FUR_MAX):
            await self.space.tick(tick)
        wool = await self.space.use('✂️')
        space = await self.space.get()
        self.assertEqual(wool, ['🧶']) # type: ignore[misc]
        self.assertEqual(space.items, ['🧶']) # type: ignore[misc]
        self.assertEqual(space.pet_fur, 0)

    async def test_use_scissors_no_pet_fur(self) -> None:
        await self.space.obtain('✂️')
        wool = await self.space.use('✂️')
        self.assertFalse(wool)

    async def test_craft(self) -> None:
        await self.space.obtain(*Space.TOOL_MATERIAL['🪓'])
        axe = await self.space.craft('🪓')
        space = await self.space.get()
        self.assertEqual(axe, '🪓')
        self.assertEqual(space.tools, [*self.space.tools, '🪓']) # type: ignore[misc]
        self.assertFalse(space.items)

    async def test_craft_furniture_item(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🪴'])
        plant = await self.space.craft('🪴')
        space = await self.space.get()
        assert isinstance(plant, Houseplant)
        self.assertEqual(await space.get_furniture(), [plant]) # type: ignore[misc]
        self.assertEqual(await self.bot.get_furniture_item(plant.id), plant)
        self.assertFalse(space.items)

    async def test_craft_unknown_blueprint(self) -> None:
        with self.assertRaisesRegex(ValueError, 'blueprint'):
            await self.space.craft('🪡')

    async def test_craft_no_resources(self) -> None:
        with self.assertRaisesRegex(ValueError, 'items'):
            await self.space.craft('🪴')

    async def test_sew(self) -> None:
        await self.space.obtain('🪡', *Space.CLOTHING_MATERIAL['🎀'])
        ribbon = await self.space.sew('🎀')
        space = await self.space.get()
        self.assertEqual(ribbon, '🎀')
        self.assertEqual(space.items, ['🎀']) # type: ignore[misc]

    async def test_sew_no_resources(self) -> None:
        await self.space.obtain('🪡')
        with self.assertRaisesRegex(ValueError, 'items'):
            await self.space.sew('🎀')

    # /clean

class PetTest(TestCase):
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

    # clean

    async def test_dress(self) -> None:
        await self.space.obtain('🎀')
        await self.pet.dress('🎀')
        space = await self.space.get()
        pet = await space.get_pet()
        self.assertEqual(pet.clothing, '🎀')
        self.assertFalse(space.items)

    async def test_dress_no_clothing(self) -> None:
        await self.space.obtain('🎀')
        await self.pet.dress('🎀')
        await self.pet.dress(None)
        space = await self.space.get()
        pet = await space.get_pet()
        self.assertIsNone(pet.clothing)
        self.assertEqual(space.items, ['🎀']) # type: ignore[misc]

class HikeTest(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.space.obtain(*Space.TOOL_MATERIAL['🧭'])
        await self.space.craft('🧭')
        self.hike = await self.space.hike()

    @staticmethod
    def pad_directions(directions: list[str]) -> list[str]:
        direction = directions[-1]
        reverse = {'➡️': '⬅️', '⬇️': '⬆️', '⬅️': '➡️', '⬆️': '⬇️'}[direction]
        return directions + list(islice(cycle((reverse, direction)), Hike.RADIUS - len(directions)))

    async def test_move(self) -> None:
        directions = self.pad_directions(self.hike.find_path('🟩'))
        move = await self.hike.move(directions)
        self.assertEqual(move, list(zip(directions, ['🟩', '✴️', '🟩', '✴️']))) # type: ignore[misc]
        self.assertFalse(self.hike.finished)

    async def test_move_destination(self) -> None:
        assert self.hike.resource
        await self.hike.move(self.pad_directions(self.hike.find_path(self.hike.resource)))
        await self.hike.move(self.hike.find_path('📍'))
        space = await self.space.get()
        self.assertTrue(self.hike.finished)
        self.assertEqual(self.hike.gathered, [self.hike.resource]) # type: ignore[misc]
        self.assertEqual(space.items, [self.hike.resource]) # type: ignore[misc]
        self.assertEqual(space.trail_supply, 0)

    async def test_move_destination_empty_space_trail_supply(self) -> None:
        assert self.hike.resource
        await self.hike.move(self.pad_directions(self.hike.find_path(self.hike.resource)))
        await self.hike.move(self.hike.find_path('📍'))
        hike = await self.space.hike()

        await hike.move(hike.find_path('📍'))
        space = await self.space.get()
        self.assertFalse(hike.gathered)
        self.assertFalse(space.items[1:])
        self.assertEqual(space.trail_supply, 0)

    async def test_move_bad_directions_length(self) -> None:
        with self.assertRaisesRegex(ValueError, 'directions'):
            await self.hike.move([])

# /clean
