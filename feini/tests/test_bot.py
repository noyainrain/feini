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

from unittest import IsolatedAsyncioTestCase

from feini import context
from feini.actions import HikeMode
from feini.bot import Bot
from feini.space import Hike, Space

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

class BotTest(FeiniTestCase):
    async def test_set_mode(self) -> None:
        mode_in = HikeMode(Hike(self.space))
        self.bot.set_mode(self.space.chat, mode_in)
        mode_out = self.bot.get_mode(self.space.chat)
        self.assertIs(mode_out, mode_in)

    async def test_create_space(self) -> None:
        space = await self.bot.create_space('local')
        pet = await space.get_pet()
        self.assertEqual(await self.bot.get_spaces(), {space}) # type: ignore[misc]
        self.assertEqual(await self.bot.get_space(space.id), space)
        self.assertEqual(await self.bot.get_space_by_chat(space.chat), space)
        self.assertEqual(pet.space_id, space.id)
        self.assertTrue(await space.get_blueprints())

# /clean
