from datetime import datetime
from time import struct_time
from typing import BinaryIO, TextIO
from urllib.request import BaseHandler

def parse(
    url_file_stream_or_string: str | bytes | TextIO | BinaryIO, etag: str | None = ...,
    modified: str | datetime | struct_time | None = ..., agent: str | None = ...,
    referrer: str | None = ..., handlers: list[BaseHandler] | None = ...,
    request_headers: dict[str, str] | None = ..., response_headers: dict[str, str] | None = ...,
    resolve_relative_uris: bool | None = ...,
    sanitize_html: bool | None = ...) -> dict[str, object]: ...

class ThingsNobodyCaresAboutButMe(Exception): ...
