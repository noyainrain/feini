from feini.items import Newspaper, Plant, Palette, Television
from feini.space import Space
from .test_space import FeiniTestCase

class PlantTest(FeiniTestCase):
    async def test_tick(self) -> None:
        await self.obtain(Space.COSTS['🪴'])
        plant = await self.space.craft('🪴')
        assert isinstance(plant, Plant)

        for _ in range(1000):
            await plant.tick(0)
            plant = await self.bot.get_object(plant.id)
            assert isinstance(plant, Plant)
            if plant.state == '🌺':
                break
        else:
            self.fail()

class TelevisionTest(FeiniTestCase):
    async def test_use(self) -> None:
        await self.obtain(Space.COSTS['📺'])
        tv = await self.space.craft('📺')
        assert isinstance(tv, Television)
        show = tv.show

        for _ in range(1000):
            await tv.use()
            tv = await self.bot.get_object(tv.id)
            assert isinstance(tv, Television)
            if tv.show != show:
                break
        else:
            self.fail()

class NewspaperTest(FeiniTestCase):
    async def test_use(self) -> None:
        await self.obtain(Space.COSTS['🗞️'])
        newspaper = await self.space.craft('🗞️')
        assert isinstance(newspaper, Newspaper)
        article = newspaper.article

        for _ in range(1000):
            await newspaper.use()
            newspaper = await self.bot.get_object(newspaper.id)
            assert isinstance(newspaper, Newspaper)
            print(_, newspaper.article)
            if newspaper.article != article:
                break
        else:
            self.fail()

class PaletteTest(FeiniTestCase):
    async def test_tick(self) -> None:
        await self.obtain(Space.COSTS['🎨'])
        palette = await self.space.craft('🎨')
        assert isinstance(palette, Palette)

        for _ in range(1000):
            await palette.tick(0)
            palette = await self.bot.get_object(palette.id)
            assert isinstance(palette, Palette)
            if palette.state == '🖼️':
                break
        else:
            self.fail()
