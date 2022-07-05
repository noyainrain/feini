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
from feini.space import Hike

class TestCase(IsolatedAsyncioTestCase):
    """Open Feini test case.

    .. attribute:: bot

       Chatbot under test.

    .. attribute:: space

       Test space.
    """

    async def asyncSetUp(self) -> None:
        self.bot = Bot(redis_url='redis:15', debug=True)
        await self.bot.redis.flushdb()
        context.bot.set(self.bot)
        self.space = await self.bot.create_space('local')

    async def asyncTearDown(self) -> None:
        await self.bot.close()

class BotTest(TestCase):
    async def test_set_mode(self) -> None:
        mode = HikeMode(Hike(self.space))
        self.bot.set_mode(self.space.chat, mode)
        self.assertIs(self.bot.get_mode(self.space.chat), mode)

    async def test_create_space(self) -> None:
        space = await self.bot.create_space('chat')
        pet = await space.get_pet()
        self.assertEqual(space.chat, 'chat')
        self.assertIn(space, await self.bot.get_spaces())
        self.assertEqual(await self.bot.get_space(space.id), space)
        self.assertEqual(await self.bot.get_space_by_chat(space.chat), space)
        self.assertEqual(pet.space_id, space.id)
        self.assertTrue(await space.get_blueprints())
        self.assertTrue(await space.get_stories())
