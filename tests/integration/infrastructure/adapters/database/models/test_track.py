from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory
from tests.unit.factories.entities.track import TrackFactory


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

    def test__from_entity__maps_provider_links(self) -> None:
        entity = TrackFactory.build()

        model = TrackModel.from_entity(entity)
        assert model.id == entity.id

        assert len(model.provider_links) == len(entity.provider_links)
        assert model.provider_links[0]["provider"] == MusicProvider.SPOTIFY.value
        assert model.provider_links[0]["provider_id"] == entity.provider_links[0].provider_id
