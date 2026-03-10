from museflow.infrastructure.adapters.database.models import AlbumDict
from museflow.infrastructure.adapters.database.models import ArtistDict

from tests.integration.factories.models.music import TrackModelFactory


class TestTrackModel:
    async def test__artist_dict(self) -> None:
        track = await TrackModelFactory.create_async(
            artists=[
                ArtistDict(
                    provider_id="unique-provider-id",
                    name="foo",
                ),
            ],
        )
        assert len(track.artists) == 1
        artist = track.artists[0]

        assert artist["provider_id"] == "unique-provider-id"
        assert artist["name"] == "foo"

    async def test__album_dict(self) -> None:
        track = await TrackModelFactory.create_async(
            album=AlbumDict(
                provider_id="unique-provider-id",
                name="foo",
                album_type="compilation",
            )
        )
        assert track.album is not None
        assert track.album["provider_id"] == "unique-provider-id"
        assert track.album["name"] == "foo"
        assert track.album["album_type"] == "compilation"
