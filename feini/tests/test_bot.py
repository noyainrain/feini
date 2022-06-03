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

from feini.actions import HikeMode
from feini.space import Hike
from feini.tests.test_space import FeiniTestCase

class BotTest(FeiniTestCase):
    async def test_get_set_mode(self) -> None:
        mode_in = HikeMode(Hike(self.space))
        self.bot.set_mode(self.space.chat, mode_in)
        mode_out = self.bot.get_mode(self.space.chat)
        self.assertIs(mode_out, mode_in)

    async def test_create_space(self) -> None:
        space = await self.bot.create_space('local')
        blueprints = await space.get_blueprints()
        self.assertTrue(blueprints)

# /clean
