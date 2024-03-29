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

from feini.furniture import Houseplant, Newspaper, Palette, Television, FURNITURE_MATERIAL
from .test_bot import TestCase

TRIALS = 1000

class HouseplantTest(TestCase):
    async def test_tick(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🪴'])
        plant = await self.space.craft('🪴')
        assert isinstance(plant, Houseplant)

        for time in range(TRIALS):
            await plant.tick(time)
            plant = await plant.get()
            if plant.state == '🌺':
                break
        else:
            self.fail()

class TelevisionTest(TestCase):
    async def test_use(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['📺'])
        tv = await self.space.craft('📺')
        assert isinstance(tv, Television)
        await tv.use()
        tv = await tv.get()
        self.assertEqual(tv.show, self.bot.tmdb.shows[0])

class NewspaperTest(TestCase):
    async def test_use(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🗞️'])
        newspaper = await self.space.craft('🗞️')
        assert isinstance(newspaper, Newspaper)
        await newspaper.use()
        newspaper = await newspaper.get()
        self.assertEqual(newspaper.article, self.bot.dw.articles[0])

class PaletteTest(TestCase):
    async def test_tick(self) -> None:
        await self.space.obtain(*FURNITURE_MATERIAL['🎨'])
        palette = await self.space.craft('🎨')
        assert isinstance(palette, Palette)

        for time in range(TRIALS):
            await palette.tick(time)
            palette = await palette.get()
            if palette.state == '🖼️':
                break
        else:
            self.fail()
