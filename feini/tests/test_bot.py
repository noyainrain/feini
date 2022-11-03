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

from asyncio import create_task
from unittest import IsolatedAsyncioTestCase

from feini import context
from feini.actions import HikeMode
from feini.bot import Bot
from feini.space import Event, Hike
from feini.util import cancel

class TestCase(IsolatedAsyncioTestCase):
    """Open Feini test case.

    .. attribute:: bot

       Chatbot under test.

    .. attribute:: space

       Test space.

    .. attribute:: events

       Events that happened during the test.
    """

    async def asyncSetUp(self) -> None:
        self.bot = Bot(redis_url='redis:15', debug=True)
        await self.bot.redis.flushdb()
        context.bot.set(self.bot)
        self.space = await self.bot.create_space('local')

        self.events: list[Event] = []
        self._events_task = create_task(self._record_events())

    async def asyncTearDown(self) -> None:
        await cancel(self._events_task)
        await self.bot.close()

    async def _record_events(self) -> None:
        async for event in self.bot.events():
            self.events.append(event)

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
        self.assertTrue(await space.get_patterns())
        self.assertTrue(await space.get_stories())
