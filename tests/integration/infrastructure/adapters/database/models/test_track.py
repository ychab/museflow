from tests.integration.factories.models.track import TrackModelFactory


class TestTrackModel:
    async def test__artists__list_of_strings(self) -> None:
        track = await TrackModelFactory.create_async(artists=["Grupo Niche", "Featured Artist"])
        assert track.artists == ["Grupo Niche", "Featured Artist"]

    async def test__album_name__string(self) -> None:
        track = await TrackModelFactory.create_async(album_name="Llegó la Salsa")
        assert track.album_name == "Llegó la Salsa"

    async def test__album_name__none(self) -> None:
        track = await TrackModelFactory.create_async(album_name=None)
        assert track.album_name is None
