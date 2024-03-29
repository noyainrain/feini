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

# pylint: disable=missing-docstring

from feini.stories import IntroStory, SewingStory
from .test_bot import TestCase

class IntroStoryTest(TestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.story = next(story for story in await self.space.get_stories()
                          if isinstance(story, IntroStory))

    async def test_tell(self) -> None:
        pet = await self.space.get_pet()

        self.bot.time += 1
        await self.story.tell()
        story = await self.story.get()
        self.assertEqual(story.chapter, 'touch')
        self.assertEqual(story.update_time, 1)
        self.assertTrue(self.events)
        self.assertEqual(self.events[-1].type, 'space-explain-touch')

        await pet.touch()
        await story.tell()
        story = await story.get()
        self.assertEqual(story.chapter, 'gather')
        self.assertEqual(self.events[-1].type, 'space-explain-gather')

        await self.space.gather()
        await story.tell()
        story = await story.get()
        self.assertEqual(story.chapter, 'feed')
        self.assertEqual(self.events[-1].type, 'space-explain-feed')

        await pet.feed('🥕')
        await story.tell()
        story = await story.get()
        self.assertEqual(story.chapter, 'craft')
        self.assertEqual(self.events[-1].type, 'space-explain-craft')

        await self.space.craft('🪓')
        await story.tell()
        self.assertNotIn(story, await self.space.get_stories())
        self.assertEqual(self.events[-1].type, 'space-explain-basics')

    async def test_tell_unmet_condition(self) -> None:
        await self.story.tell()
        self.bot.time += 1
        await self.story.tell()
        story = await self.story.get()
        self.assertEqual(story.chapter, 'touch')
        self.assertEqual(story.update_time, 0)

class SewingStoryTest(TestCase):
    async def test_tell(self) -> None:
        story = next(story for story in await self.space.get_stories()
                     if isinstance(story, SewingStory))

        await self.space.obtain('✂️')
        await story.tell()
        story = await story.get()
        self.assertEqual(story.chapter, 'visit')

        self.bot.time += 2
        await story.tell()
        story = await story.get()
        characters = await self.space.get_characters()
        self.assertEqual(len(characters), 1)
        ghost = characters[0]
        dialogue = await ghost.get_dialogue()
        self.assertEqual(story.chapter, 'quest')
        self.assertEqual(ghost.avatar, '👻')
        self.assertTrue(dialogue)
        self.assertEqual(dialogue[0].id, 'initial')
        self.assertTrue(self.events)
        self.assertEqual(self.events[0].type, 'space-visit-ghost')

        await ghost.talk()
        await ghost.talk()
        await ghost.talk()
        await self.space.obtain('🧶', '🧶', '🧶')
        await ghost.talk()
        await story.tell()
        story = await story.get()
        self.assertEqual(story.chapter, 'leave')
        self.assertIn('🪡', await self.space.get_blueprints())

        await ghost.talk()
        await story.tell()
        self.assertNotIn(story, await self.space.get_stories())
        self.assertFalse(await self.space.get_characters())
