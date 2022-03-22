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

"""Various utilities."""

from __future__ import annotations

from asyncio import CancelledError, Task
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import random
import re
import string
import sys
from typing import Awaitable, Type, TypeVar, cast, overload
import unicodedata

from aiohttp import ClientResponse, ClientResponseError
import aioredis.client
from aioredis.client import AnyFieldT, ExpiryT, FieldT, KeyT, KeysT, TimeoutSecT
from aioredis.connection import EncodableT

_T = TypeVar('_T')

def truncate(text: str, length: int = 16) -> str:
    """Truncate *text* at *length*.

    A truncated text ends with an ellipsis character.
    """
    return f'{text[:length - 1]}…' if len(text) > length else text

def isemoji(char: str) -> bool:
    """Guess if *char* is an emoji.

    True if the character is categorized as other symbol, with an optional presentation selector.
    """
    return (
        1 <= len(char) <= 2 and unicodedata.category(char[0]) == 'So' and
        (len(char) == 1 or char[1] in '\N{VARIATION SELECTOR-15}\N{VARIATION SELECTOR-16}'))

async def raise_for_status(response: ClientResponse) -> None:
    """Raise a ClientResponseError if the *response* status is 400 or higher.

    The server error message is included.
    """
    if not response.ok:
        message = truncate(re.sub(r'\s+', ' ', await response.text()), 1024)
        raise ClientResponseError(response.request_info, response.history, status=response.status,
                                  message=message, headers=response.headers)

class JSONObject(dict[str, object]):
    """JSON object providing type safe member access."""

    @overload
    def get(self, key: str, default: object = None, *, cls: None = None) -> object:
        pass
    @overload
    def get(self, key: str, *, cls: Type[_T]) -> _T:
        pass
    @overload
    def get(self, key: str, default: _T, *, cls: Type[_T]) -> _T:
        pass
    def get(self, key: str, default: object = None, *, # type: ignore[misc]
            cls: Type[_T] | None = None) -> object:
        """Return the value for *key*.

        *cls* is the value's expected type and a :exc:`TypeError` is raised if validation fails.
        """
        value = super().get(key, default)
        if cls and not isinstance(value, cls):
            raise TypeError(f'Bad {key} type {type(value).__name__}')
        return value

# /clean

@contextmanager
def recovery() -> Iterator[None]:
    """Return a context manager that recovers from unhandled exceptions in the block.

    Conceptionally, the block is executed on its own stack, without the overhead of creating a
    thread or task.
    """
    try:
        # pylint: disable=broad-except
        yield
    except Exception:
        sys.excepthook(*sys.exc_info())

async def cancel(task: Task[None]) -> None:
    """Cancel the *task*."""
    task.cancel()
    try:
        await task
    except CancelledError:
        pass

def randstr(length: int = 16, charset: str = string.ascii_lowercase) -> str:
    """Generate a random string.

    The string will have the given *length* and consist of characters from *charset*.
    """
    return ''.join(random.choice(charset) for i in range(length))

class Redis(aioredis.client.Redis):
    async def close(self) -> None:
        await cast(Awaitable[None], super().close()) # type: ignore[no-untyped-call]

    def pipeline(self, transaction: bool = True, shard_hint: str | None = None) -> Pipeline:
        return cast(Pipeline, super().pipeline(transaction, shard_hint))

    def blpop(self, keys: KeysT, timeout: TimeoutSecT = 0) -> Awaitable[tuple[str, str]]:
        return cast(Awaitable[tuple[str, str]], super().blpop(keys, timeout))

    def get(self, name: KeyT) -> Awaitable[str | None]:
        return cast('Awaitable[str | None]', super().get(name))

    def hexists(self, name: KeyT, key: FieldT) -> Awaitable[bool]:
        return cast(Awaitable[bool], super().hexists(name, key))

    def hget(self, name: KeyT, key: FieldT) -> Awaitable[str | None]:
        return cast('Awaitable[str | None]', super().hget(name, key))

    def hgetall(self, name: KeyT) -> Awaitable[dict[str, str]]:
        return cast(Awaitable[dict[str, str]], super().hgetall(name))

    def hset(self, name: KeyT, key: FieldT | None = None, value: EncodableT | None = None,
             mapping: Mapping[AnyFieldT, EncodableT] | None = None) -> Awaitable[int]:
        return cast(Awaitable[int], super().hset(name, key, value, mapping))

    def hvals(self, name: KeyT) -> Awaitable[list[str]]:
        return cast(Awaitable[list[str]], super().hvals(name))

    def lrange(self, name: KeyT, start: int, end: int) -> Awaitable[list[str]]:
        return cast(Awaitable[list[str]], super().lrange(name, start, end))

    def llen(self, name: KeyT) -> Awaitable[int]:
        return cast(Awaitable[int], super().llen(name))

    def set(
        self, name: KeyT, value: EncodableT, ex: ExpiryT | None = None, px: ExpiryT | None = None,
        nx: bool = False, xx: bool = False, keepttl: bool = False
    ) -> Awaitable[None]:
        return cast(Awaitable[None], super().set(name, value, ex, px, nx, xx, keepttl))

class Pipeline(aioredis.client.Pipeline, Redis):
    def multi(self) -> None:
        self.multi()

    async def execute(self, raise_on_error: bool = True) -> list[object]:
        return await self.execute(raise_on_error)

    async def watch(self, *names: KeyT) -> None:
        return await cast(Awaitable[None], super().watch(*names))
