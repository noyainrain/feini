"""TODO."""

from __future__ import annotations

import random
import string

import aioredis.client
from aioredis.client import KeyT, FieldT, AnyFieldT
from aioredis.connection import EncodableT

from collections.abc import Mapping

from typing import Type, TypeVar, overload, Literal, cast, Awaitable

_T = TypeVar('_T')

def randstr(length: int = 16, charset: str = string.ascii_lowercase) -> str:
    """Generate a random string.

    The string will have the given *length* and consist of characters from *charset*.
    """
    return ''.join(random.choice(charset) for i in range(length))

class Redis(aioredis.client.Redis):
    def hget(self, name: KeyT, key: FieldT) -> Awaitable[str | None]:
        return cast('Awaitable[str | None]', super().hget(name, key))

    def hset(self, name: KeyT, key: FieldT | None = None, value: EncodableT | None = None,
             mapping: Mapping[AnyFieldT, EncodableT] | None = None) -> Awaitable[int]:
        return cast(Awaitable[int], super().hset(name, key, value, mapping))

    def lrange(self, name: KeyT, start: int, end: int) -> Awaitable[list[str]]:
        return cast(Awaitable[list[str]], super().lrange(name, start, end))

    def llen(self, name: KeyT) -> Awaitable[int]:
        return cast(Awaitable[int], super().llen(name))

    def pipeline(self, transaction: bool = True, shard_hint: str | None = None) -> Pipeline:
        return cast(Pipeline, super().pipeline(transaction, shard_hint))

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
