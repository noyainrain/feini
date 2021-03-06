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

from feini.furniture import FURNITURE_MATERIAL
from feini.space import Space
from .test_bot import TestCase

class Test(TestCase):
    async def test(self) -> None:
        # Play with space
        reply = await self.bot.perform('local', 'โบ')
        self.assertEqual(reply[0], 'โบ')

        reply = await self.bot.perform('local', '๐งบ')
        self.assertEqual(reply[0], '๐งบ')

        reply = await self.bot.perform('local', '๐ชจ')
        self.assertEqual(reply[0], '๐ชจ')

        reply = await self.bot.perform('local', '๐จ๐ช')
        self.assertEqual(reply[0], '๐จ')

        reply = await self.bot.perform('local', '๐ช')
        self.assertEqual(reply[0], '๐ช')

        await self.bot.perform('local', f"obtain ๐ชก{''.join(Space.CLOTHING_MATERIAL['๐'])}")
        reply = await self.bot.perform('local', '๐ชก๐')
        self.assertEqual(reply[0], '๐ชก')

        # Play with pet
        reply = await self.bot.perform('local', '๐')
        self.assertEqual(reply[0], '๐ฅ')

        reply = await self.bot.perform('local', '๐ฅ')
        self.assertEqual(reply[:2], '๐ฅ๐')

        reply = await self.bot.perform('local', '๐งฝ')
        self.assertEqual(reply[:2], '๐งฝ๐')

        reply = await self.bot.perform('local', '๐')
        self.assertEqual(reply[:2], '๐๐')

        await self.bot.perform('local', 'obtain โ๏ธ')
        reply = await self.bot.perform('local', 'โ๏ธ')
        self.assertIn('later', reply)

        reply = await self.bot.perform('local', 'โ๏ธ Frank')
        self.assertEqual(reply[:3], 'โ๏ธ๐')

        # Play with furniture
        for piece, material in FURNITURE_MATERIAL.items():
            await self.bot.perform('local', f"obtain {''.join(material)}")
            await self.bot.perform('local', f'๐จ{piece}')

        reply = await self.bot.perform('local', '๐ช')
        self.assertEqual(reply[0], '๐ช')

        reply = await self.bot.perform('local', 'โพ')
        self.assertEqual(reply[0], 'โพ')

        reply = await self.bot.perform('local', '๐งธ')
        self.assertEqual(reply[0], '๐งธ')

        reply = await self.bot.perform('local', '๐๏ธ')
        self.assertEqual(reply[:2], '๐๏ธ')

        reply = await self.bot.perform('local', '๐ชด')
        self.assertEqual(reply[0], '๐ชด')

        reply = await self.bot.perform('local', 'โฒ')
        self.assertEqual(reply[0], 'โฒ')

        reply = await self.bot.perform('local', '๐บ')
        self.assertEqual(reply[0], '๐บ')

        reply = await self.bot.perform('local', '๐๏ธ')
        self.assertEqual(reply[:2], '๐๏ธ')

        reply = await self.bot.perform('local', '๐จ')
        self.assertEqual(reply[0], '๐จ')

        # Play with character
        reply = await self.bot.perform('local', '๐ป')
        self.assertIn('here', reply)
