# pylint: disable=all

from collections.abc import Callable
from typing import Generic, Literal, TypeVar

_C = TypeVar('_C', bound=ServerConnection)

class ServerConnection:
    server: str
    port: int
    nickname: str
    password: str | None
    username: str
    ircname: str

    def add_global_handler(self: _C, event: str, handler: Callable[[_C, Event], object],
                           priority: int = ...) -> None: ...
    def remove_global_handler(self: _C, event: str,
                              handler: Callable[[_C, Event], object]) -> int: ...
    def cap(self, subcommand: str, *args: str) -> None: ...
    def disconnect(self, message: str = ...) -> None: ...
    def join(self, channel: str, key: str = ...) -> None: ...
    def privmsg(self, target: str, text: str) -> None: ...
    def send_items(self, *items: str) -> None: ...

class Reactor(Generic[_C]):
    connection_class: _C

    def server(self) -> _C: ...

class Event:
    type: str
    source: str
    target: str
    arguments: list[str]
