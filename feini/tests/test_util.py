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

from unittest import TestCase

from feini.util import isemoji

class IsEmojiTest(TestCase):
    def test(self) -> None:
        self.assertTrue(isemoji('⭐'))

    def test_presentation_selector(self) -> None:
        self.assertTrue(isemoji('⭐︎'))

    def test_letter(self) -> None:
        self.assertFalse(isemoji('A'))

    def test_string(self) -> None:
        self.assertFalse(isemoji('⭐A'))
