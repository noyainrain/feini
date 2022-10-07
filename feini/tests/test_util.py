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

from asyncio import Task, create_task, sleep
from string import ascii_lowercase
from unittest import IsolatedAsyncioTestCase, TestCase

from aiohttp import ClientResponseError, web
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp.web import Application, HTTPNotImplemented, Request, Response

from feini.util import JSONObject, cancel, collapse, isemoji, raise_for_status, randstr, truncate

class RandstrTest(TestCase):
    def test(self) -> None:
        string = randstr()
        self.assertEqual(len(string), 16)
        self.assertLessEqual(set(string), set(ascii_lowercase)) # type: ignore[misc]

class TruncateTest(TestCase):
    def test(self) -> None:
        self.assertEqual(truncate('Meow! Meow!', 5), 'Meow…')

    def test_short_text(self) -> None:
        self.assertEqual(truncate('Meow!', 5), 'Meow!')

class IsEmojiTest(TestCase):
    def test(self) -> None:
        self.assertTrue(isemoji('⭐'))

    def test_presentation_selector(self) -> None:
        self.assertTrue(isemoji('⭐︎'))

    def test_letter(self) -> None:
        self.assertFalse(isemoji('A'))

    def test_string(self) -> None:
        self.assertFalse(isemoji('⭐A'))

class CollapseTest(TestCase):
    def test(self) -> None:
        text = collapse('Meow,  meow!\nMeow!␟')
        self.assertEqual(text, 'Meow, meow! Meow!')

class CancelTest(IsolatedAsyncioTestCase):
    async def test(self) -> None:
        task: Task[None] = create_task(sleep(1))
        await cancel(task)
        self.assertTrue(task.cancelled())

class RaiseForStatusTest(AioHTTPTestCase):
    @staticmethod
    async def index(request: Request) -> Response:
        raise HTTPNotImplemented(text='Not  implemented')

    async def get_application(self) -> Application:
        app = Application()
        app.add_routes([web.get('/', self.index)])
        return app

    async def test(self) -> None:
        response = await self.client.get('/')
        with self.assertRaisesRegex(ClientResponseError, 'Not implemented'):
            await raise_for_status(response)

class JSONObjectTest(TestCase):
    def setUp(self) -> None:
        self.cat = JSONObject(name='Frank')

    def test_get(self) -> None:
        self.assertEqual(self.cat.get('name', cls=str), 'Frank')

    def test_get_bad_item_type(self) -> None:
        with self.assertRaisesRegex(TypeError, 'name'):
            self.cat.get('name', cls=int)
