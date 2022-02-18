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

from collections.abc import Mapping
import random
import string
from typing import Awaitable, Literal, Type, TypeVar, cast, overload
import unicodedata

import aioredis.client
from aioredis.client import AnyFieldT, ExpiryT, FieldT, KeyT, KeysT, TimeoutSecT
from aioredis.connection import EncodableT

_T = TypeVar('_T')

def isemoji(char: str) -> bool:
    """Guess if *char* is an emoji.

    True if the character is categorized as other symbol, with an optional presentation selector.
    """
    return (
        1 <= len(char) <= 2 and unicodedata.category(char[0]) == 'So' and
        (len(char) == 1 or char[1] in '\N{VARIATION SELECTOR-15}\N{VARIATION SELECTOR-16}'))

# / Clean

def randstr(length: int = 16, charset: str = string.ascii_lowercase) -> str:
    """Generate a random string.

    The string will have the given *length* and consist of characters from *charset*.
    """
    return ''.join(random.choice(charset) for i in range(length))

class Redis(aioredis.client.Redis):
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

class JSONObject:
    def __init__(self, data: dict[str, object]) -> None:
        self.data = data

    @overload
    def get(self, key: str, cls: Type[_T], *, optional: Literal[False] = False) -> _T:
        pass
    @overload
    def get(self, key: str, cls: Type[_T], *, optional: Literal[True]) -> _T | None:
        pass
    def get(self, key: str, cls: Type[_T], *, optional: bool = False) -> _T | None:
        value = self.data.get(key)
        if optional and value is None:
            return None
        if issubclass(cls, JSONObject):
            if not isinstance(value, dict):
                raise TypeError(f'Invalid {key} type {type(value).__name__}')
            return cast(_T, cls(value))
        if not isinstance(value, cls):
            raise TypeError(f'Invalid {key} type {type(value).__name__}')
        return value

    #@overload
    #def get_object(self, key: str, *, optional: Literal[False] = False) -> JSONObject:
    #    pass
    #@overload
    #def get_object(self, key: str, *, optional: Literal[True]) -> JSONObject | None:
    #    pass
    #def get_object(self, key: str, *, optional: bool = False) -> JSONObject | None:
    #    value = self.get(key, dict, optional=True) if optional else self.get(key, dict)
    #    return JSONObject(value) if value else None
