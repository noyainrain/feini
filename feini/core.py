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

"""Core concepts."""

from typing import TypeVar

from . import context

_E = TypeVar('_E', bound='Entity')

class Entity:
    """Game entity.

    .. attribute:: id

       Unique entity ID.
    """

    def __init__(self, data: dict[str, str]) -> None:
        self.id = data['id']

    async def get(self: _E) -> _E:
        """Get a fresh copy of the entity."""
        data = await context.bot.get().redis.hgetall(self.id)
        if not data:
            raise ReferenceError(self.id)
        return type(self)(data)

    def __repr__(self) -> str:
        return f'<{self.id}>'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
