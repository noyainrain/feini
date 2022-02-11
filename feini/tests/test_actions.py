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
        reply = await self.bot.perform('local', '⛺')
        self.assertEqual(reply[0], '⛺')

        reply = await self.bot.perform('local', '🧺')
        self.assertEqual(reply[0], '🧺')

        reply = await self.bot.perform('local', '🪨')
        self.assertEqual(reply[0], '🪨')

        reply = await self.bot.perform('local', '🔨🪓')
        self.assertEqual(reply[0], '🔨')

        reply = await self.bot.perform('local', '🪓')
        self.assertEqual(reply[0], '🪓')

        await self.bot.perform('local', f"obtain 🪡{''.join(Space.CLOTHING_MATERIAL['🎀'])}")
        reply = await self.bot.perform('local', '🪡🎀')
        self.assertEqual(reply[0], '🪡')

        # Play with pet
        reply = await self.bot.perform('local', '👋')
        self.assertEqual(reply[0], '🥚')

        reply = await self.bot.perform('local', '🥕')
        self.assertEqual(reply[:2], '🥕🐕')

        reply = await self.bot.perform('local', '🧽')
        self.assertEqual(reply[:2], '🧽🐕')

        reply = await self.bot.perform('local', '🎀')
        self.assertEqual(reply[:2], '🐕🎀')

        await self.bot.perform('local', 'obtain ✂️')
        reply = await self.bot.perform('local', '✂️')
        self.assertIn('later', reply)

        reply = await self.bot.perform('local', '✏️ Frank')
        self.assertEqual(reply[:3], '✏️🐕')

        # Play with furniture
        for piece, material in FURNITURE_MATERIAL.items():
            await self.bot.perform('local', f"obtain {''.join(material)}")
            await self.bot.perform('local', f'🔨{piece}')

        reply = await self.bot.perform('local', '🪃')
        self.assertEqual(reply[0], '🪃')

        reply = await self.bot.perform('local', '⚾')
        self.assertEqual(reply[0], '⚾')

        reply = await self.bot.perform('local', '🧸')
        self.assertEqual(reply[0], '🧸')

        reply = await self.bot.perform('local', '🛋️')
        self.assertEqual(reply[:2], '🛋️')

        reply = await self.bot.perform('local', '🪴')
        self.assertEqual(reply[0], '🪴')

        reply = await self.bot.perform('local', '⛲')
        self.assertEqual(reply[0], '⛲')

        reply = await self.bot.perform('local', '📺')
        self.assertEqual(reply[0], '📺')

        reply = await self.bot.perform('local', '🗞️')
        self.assertEqual(reply[:2], '🗞️')

        reply = await self.bot.perform('local', '🎨')
        self.assertEqual(reply[0], '🎨')

        # Play with character
        reply = await self.bot.perform('local', '👻')
        self.assertIn('here', reply)
