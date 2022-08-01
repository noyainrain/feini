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

from itertools import cycle, islice

from feini.furniture import Houseplant, FURNITURE_MATERIAL
from feini.space import Hike, Pet, Space
from feini.stories import SewingStory
from .test_bot import TestCase

class SpaceTest(TestCase):
    async def test_tick(self) -> None:
        await self.space.tick(0)
        space = await self.space.get()
        pet = await space.get_pet()
        self.assertEqual(space.time, 1)
        self.assertEqual(space.meadow_vegetable_growth, Space.MEADOW_VEGETABLE_GROWTH_MAX + 1)
        self.assertEqual(space.woods_growth, Space.WOODS_GROWTH_MAX + 1)
        self.assertEqual(space.trail_supply, Space.TRAIL_SUPPLY_MAX + 1)
        self.assertEqual(pet.nutrition, (8 - 1) - 1)

    async def test_obtain(self) -> None:
        await self.space.obtain('🪵', '🧶', '🥕')
        await self.space.obtain('🪵')
        space = await self.space.get()
        self.assertEqual(space.items, ['🥕', '🪵', '🪵', '🧶']) # type: ignore[misc]

    async def test_gather(self) -> None:
        resources = await self.space.gather()
        space = await self.space.get()
        self.assertEqual(resources, ['🥕', '🪨']) # type: ignore[misc]
        self.assertEqual(space.items, resources)
        self.assertEqual(space.meadow_vegetable_growth, 0)

    async def test_gather_immature_vegetable(self) -> None:
        await self.space.gather()
        resources = await self.space.gather()
        self.assertFalse(resources)

    async def test_chop_wood(self) -> None:
        await self.space.obtain('🪓', '🥕')
        wood = await self.space.chop_wood()
        space = await self.space.get()
        self.assertEqual(wood, ['🪵']) # type: ignore[misc]
        self.assertEqual(space.items, ['🥕', '🪵']) # type: ignore[misc]
        self.assertEqual(space.woods_growth, 0)

    async def test_chop_wood_immature_wood(self) -> None:
        await self.space.obtain('🪓')
        await self.space.chop_wood()
        wood = await self.space.chop_wood()
        self.assertFalse(wood)

    async def test_craft(self) -> None:
        await self.space.obtain(*Space.TOOL_MATERIAL['🪓'], '🥕')
        axe = await self.space.craft('🪓')
        space = await self.space.get()
        self.assertEqual(axe, '🪓')
        self.assertEqual(space.tools, [*self.space.tools, '🪓']) # type: ignore[misc]
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

    async def test_craft_furniture_item(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🪴'], '🥕')
        plant = await self.space.craft('🪴')
        space = await self.space.get()
        assert isinstance(plant, Houseplant)
        self.assertEqual(await space.get_furniture(), [plant]) # type: ignore[misc]
        self.assertEqual(await self.bot.get_furniture_item(plant.id), plant)
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

    async def test_craft_unknown_blueprint(self) -> None:
        with self.assertRaisesRegex(ValueError, 'blueprint'):
            await self.space.craft('🪡')

    async def test_craft_no_material(self) -> None:
        with self.assertRaisesRegex(ValueError, 'items'):
            await self.space.craft('🪴')

    async def test_sew(self) -> None:
        await self.space.obtain('🪡', *Space.CLOTHING_MATERIAL['🎀'], '🥕')
        ribbon = await self.space.sew('🎀')
        space = await self.space.get()
        self.assertEqual(ribbon, '🎀')
        self.assertEqual(space.items, ['🥕', '🎀']) # type: ignore[misc]

    async def test_sew_no_material(self) -> None:
        await self.space.obtain('🪡')
        with self.assertRaisesRegex(ValueError, 'items'):
            await self.space.sew('🎀')

class PetTest(TestCase):
    TRIALS = 1000

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.pet = await self.space.get_pet()

    async def test_tick(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🪴'])
        await self.space.craft('🪴')
        await self.pet.tick()
        pet = await self.pet.get()
        space = await self.space.get()
        self.assertEqual(pet.nutrition, (8 - 1) - 1)
        self.assertEqual(pet.dirt, Pet.DIRT_MAX - (8 - 1) + 1)
        self.assertEqual(pet.fur, 1)

        for _ in range(self.TRIALS):
            if pet.activity_id != '':
                break
            await self.pet.tick()
            pet = await self.pet.get()
        else:
            self.fail()

    async def test_touch(self) -> None:
        await self.pet.touch()
        pet = await self.pet.get()
        self.assertTrue(pet.hatched)

    async def test_feed(self) -> None:
        await self.space.obtain('🥕', '🥕')
        await self.pet.feed('🥕')
        pet = await self.pet.get()
        space = await self.space.get()
        self.assertEqual(pet.nutrition, Pet.NUTRITION_MAX)
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

    async def test_feed_full_pet(self) -> None:
        await self.space.obtain('🥕')
        await self.pet.feed('🥕')
        with self.assertRaisesRegex(ValueError, 'nutrition'):
            await self.pet.feed('🥕')

    async def test_feed_no_vegetable(self) -> None:
        with self.assertRaisesRegex(ValueError, 'items'):
            await self.pet.feed('🥕')

    async def test_wash(self) -> None:
        await self.pet.wash()
        pet = await self.pet.get()
        self.assertEqual(pet.dirt, 0)

    async def test_wash_clean_pet(self) -> None:
        await self.pet.wash()
        with self.assertRaisesRegex(ValueError, 'dirt'):
            await self.pet.wash()

    async def test_dress(self) -> None:
        await self.space.obtain('🎀', '🥕')
        await self.pet.dress('🎀')
        pet = await self.pet.get()
        space = await self.space.get()
        self.assertEqual(pet.clothing, '🎀')
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

    async def test_dress_no_clothing(self) -> None:
        await self.space.obtain('🎀', '🥕')
        await self.pet.dress('🎀')
        await self.pet.dress(None)
        pet = await self.pet.get()
        space = await self.space.get()
        self.assertIsNone(pet.clothing)
        self.assertEqual(space.items, ['🥕', '🎀']) # type: ignore[misc]

    async def test_shear(self) -> None:
        await self.space.obtain('✂️', '🥕')
        for tick in range(Pet.FUR_MAX):
            await self.space.tick(tick)
        wool = await self.pet.shear()
        pet = await self.pet.get()
        space = await self.space.get()
        self.assertEqual(wool, ['🧶']) # type: ignore[misc]
        self.assertEqual(pet.fur, 0)
        self.assertEqual(space.items, ['🥕', '🧶']) # type: ignore[misc]

    async def test_shear_immature_fur(self) -> None:
        await self.space.obtain('✂️')
        wool = await self.pet.shear()
        self.assertFalse(wool)

    async def test_change_name(self) -> None:
        await self.pet.change_name('Frank  ')
        pet = await self.pet.get()
        self.assertEqual(pet.name, 'Frank')

class CharacterTest(TestCase):
    async def test_talk(self) -> None:
        story = next(story for story in await self.space.get_stories()
                     if isinstance(story, SewingStory))
        await self.space.obtain('✂️', '🥕')
        await story.tell()
        self.bot.time += 2
        await story.tell()
        character = next(iter(await self.space.get_characters()))

        message = await character.talk()
        dialogue = await character.get_dialogue()
        self.assertEqual(message.id, 'ghost-sewing-hello')
        self.assertEqual(dialogue[0], message)

        await character.talk()
        await character.talk()
        message = await character.talk()
        space = await self.space.get()
        self.assertEqual(message.id, 'ghost-sewing-request')
        self.assertFalse(message.taken)
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

        await space.obtain('🧶', '🧶', '🧶')
        message = await character.talk()
        space = await self.space.get()
        self.assertEqual(message.id, 'ghost-sewing-blueprint')
        self.assertEqual(message.taken, ['🧶', '🧶', '🧶']) # type: ignore[misc]
        self.assertEqual(space.items, ['🥕']) # type: ignore[misc]

        await character.talk()
        message = await character.talk()
        self.assertEqual(message.id, 'ghost-sewing-goodbye')

class HikeTest(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.space.obtain('🧭')
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
