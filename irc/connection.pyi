# pylint: disable=all

from socket import socket
from ssl import SSLContext

class AioFactory:
    def __init__(
        self, *, ssl: SSLContext | bool = ..., family: int = ..., proto: int = ...,
        flags: int = ..., local_addr: tuple[str, int] | None = ...,
        server_hostname: str | None = ..., ssl_handshake_timeout: float | None = ...,
        happy_eyeballs_delay: float | None = ..., interleave: int | None = ...) -> None: ...
