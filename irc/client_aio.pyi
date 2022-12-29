# pylint: disable=all

from .client import Reactor, ServerConnection
from .connection import AioFactory

class AioConnection(ServerConnection):
    connect_factory: AioFactory

    async def connect(
        self, server: str, port: int, nickname: str, password: str | None = ...,
        username: str | None = ..., ircname: str | None = ...,
        connect_factory: AioFactory = ...) -> None: ...

class AioReactor(Reactor[AioConnection]): ...
