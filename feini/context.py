"""TODO."""

from __future__ import annotations

from contextvars import ContextVar
import typing

if typing.TYPE_CHECKING:
    from .bot import Bot

bot: ContextVar[Bot] = ContextVar('bot')
