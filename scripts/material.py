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

"""Show material distribution information."""

# pylint: disable=import-error,wrong-import-position

from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from feini.space import Space

MATERIAL = (
    {obj: material for obj, material in Space.COSTS.items() if obj not in {'🪓', '🪃'}} |
    Space.CLOTHING_MATERIAL)
INCOME = {'🪨': 1, '🪵': 1, '🧶': 1}
TARGET_CRAFT_TIME = 2

def print_metric(label: str, value: float, target: float | None = None) -> None:
    """Print a metric *value* with the given *label* and an optional *target* value."""
    target_text = f'/ {target:.1f} ({value - target:+.1f})' if target else ''
    print(f'{label}: {value:.1f} {target_text}'.rstrip())

object_count = len(MATERIAL)
total_income = sum(INCOME.values())
resources = [resource for resources in MATERIAL.values() for resource in resources]
distribution = {resource: resources.count(resource) for resource in INCOME}
total_resources = sum(distribution.values())

print_metric('Objects', object_count)
print_metric('Income (1 / d)', total_income)
for resource, income in INCOME.items():
    print_metric(f'    {resource}', income)
print_metric('Total object resources', total_resources,
             total_income * TARGET_CRAFT_TIME * object_count)
for resource, count in distribution.items():
    print_metric(f'    {resource}', count, INCOME[resource] * TARGET_CRAFT_TIME * object_count)
print_metric('Average object resources', total_resources / object_count,
             total_income * TARGET_CRAFT_TIME)
print_metric('Total object craft time (d)', total_resources / total_income,
             TARGET_CRAFT_TIME * object_count)
print_metric('Average object craft time (d)', total_resources / total_income / object_count,
             TARGET_CRAFT_TIME)
print_metric(
    'Maximum object craft time (d)',
    max(count / INCOME[resource] / object_count for resource, count in distribution.items()),
    TARGET_CRAFT_TIME)
