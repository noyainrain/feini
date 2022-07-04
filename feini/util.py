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
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
import random
import re
from string import ascii_lowercase
import sys
from typing import Literal, Type, TypeVar, overload
import unicodedata

from aiohttp import ClientResponse, ClientResponseError
import aioredis.client
from aioredis.client import AnyFieldT, AnyKeyT, FieldT, KeyT, KeysT, TimeoutSecT
from aioredis.connection import EncodableT

_T = TypeVar('_T')

def randstr(length: int = 16, *, charset: str = ascii_lowercase) -> str:
    """Generate a random string.

    The string will have the given *length* and consist of characters from *charset*.
    """
    return ''.join(random.choice(charset) for _ in range(length))

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

async def cancel(task: Task[_T]) -> None:
    """Cancel the *task*."""
    task.cancel()
    try:
        await task
    except CancelledError:
        pass

async def raise_for_status(response: ClientResponse) -> None:
    """Raise a ClientResponseError if the *response* status is 400 or higher.

    The server error message is included.
    """
    if not response.ok:
        message = truncate(re.sub(r'\s+', ' ', await response.text()), 1024)
        raise ClientResponseError(response.request_info, response.history, status=response.status,
                                  message=message, headers=response.headers)

@contextmanager
def recovery() -> Iterator[None]:
    """Context manager which recovers from unhandled exceptions in the block.

    Conceptionally, the block is executed on its own stack, without the overhead of creating a
    thread or task.
    """
    # pylint: disable=broad-except
    try:
        yield
    except Exception:
        sys.excepthook(*sys.exc_info())

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

class Redis(aioredis.client.Redis):
    """Supplemented Redis client type annotations."""

    # pylint: disable=multiple-statements

    def pipeline(self, transaction: bool = ..., shard_hint: str | None = ...) -> Pipeline: ...
    async def close(self) -> None: ...

    def blpop(self, keys: KeysT,
              timeout: TimeoutSecT = ...) -> Awaitable[tuple[str, str] | None]: ...
    def exists(self, *names: KeyT) -> Awaitable[int]: ...
    def flushdb(self, asynchronous: bool = ...) -> Awaitable[bool]: ...
    def hexists(self, name: KeyT, key: FieldT) -> Awaitable[bool]: ...
    def hget(self, name: KeyT, key: FieldT) -> Awaitable[str | None]: ...
    def hgetall(self, name: KeyT) -> Awaitable[dict[str, str]]: ...
    def hmget(self, name: KeyT, keys: Sequence[KeyT],
              *args: FieldT) -> Awaitable[list[str | None]]: ...
    def hset(self, name: KeyT, key: FieldT | None = ..., value: EncodableT | None = ...,
             mapping: Mapping[AnyFieldT, EncodableT] | None = ...) -> Awaitable[int]: ...
    def hvals(self, name: KeyT) -> Awaitable[list[str]]: ...
    def lrange(self, name: KeyT, start: int, end: int) -> Awaitable[list[str]]: ...
    def smembers(self, name: KeyT) -> Awaitable[list[str]]: ...
    def zadd(self, name: KeyT, mapping: Mapping[AnyKeyT, EncodableT], nx: bool = ...,
             xx: bool = ..., ch: bool = ..., incr: bool = ...) -> Awaitable[int | float | None]: ...

    @overload # type: ignore[override]
    def zrange(self, name: KeyT, start: int, end: int, desc: bool,
               withscores: Literal[True]) -> Awaitable[list[tuple[str, float]]]: ...
    @overload
    def zrange(self, name: KeyT, start: int, end: int, desc: bool, withscores: Literal[True],
               score_cast_func: Callable[[str], _T]) -> Awaitable[list[tuple[str, _T]]]: ...
    @overload
    def zrange(self, name: KeyT, start: int, end: int, desc: bool = ..., *,
               withscores: Literal[True]) -> Awaitable[list[tuple[str, float]]]: ...
    @overload
    def zrange(
        self, name: KeyT, start: int, end: int, desc: bool = ..., *, withscores: Literal[True],
        score_cast_func: Callable[[str], _T]) -> Awaitable[list[tuple[str, _T]]]: ...
    @overload
    def zrange(
        self, name: KeyT, start: int, end: int, desc: bool = ..., withscores: Literal[False] = ...,
        score_cast_func: Callable[[str], _T] = ...
    ) -> Awaitable[list[str]]: ...
    def zrange(
        self, name: KeyT, start: int, end: int, desc: bool = ..., withscores: bool = ...,
        score_cast_func: Callable[[str], _T] = ...
    ) -> Awaitable[list[str] | list[tuple[str, _T]]]: ...

    def zscore(self, name: str, value: EncodableT) -> Awaitable[float | None]: ...

class Pipeline(aioredis.client.Pipeline, Redis):
    """Supplemented Redis pipeline type annotations."""

    # pylint: disable=multiple-statements

    def multi(self) -> None: ...
    async def execute(self, raise_on_error: bool = True) -> list[object]: ...
    async def watch(self, *names: KeyT) -> bool: ...
