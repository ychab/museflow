from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import delete_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestDeleteLogic:
    async def test__nominal__by_artist(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        await TrackModelFactory.create_async(user_id=user.id, artists=["Portishead"])

        result = await delete_logic(
            email=user.email, artist="Radiohead", name=None, source=None, provider=None, yes=True
        )
        assert result.deleted_count == 1

        remaining = await delete_logic(
            email=user.email, artist="Portishead", name=None, source=None, provider=None, yes=True
        )
        assert remaining.deleted_count == 1

    async def test__nominal__by_artist_and_name(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")

        result = await delete_logic(
            email=user.email, artist="Radiohead", name="Creep", source=None, provider=None, yes=True
        )
        assert result.deleted_count == 1

        remaining = await delete_logic(
            email=user.email, artist="Radiohead", name="Karma Police", source=None, provider=None, yes=True
        )
        assert remaining.deleted_count == 1

    async def test__purge__all_tracks(self, user: User) -> None:
        await TrackModelFactory.create_batch_async(size=5, user_id=user.id)

        result = await delete_logic(
            email=user.email, artist=None, name=None, source=None, provider=None, purge=True, yes=True
        )
        assert result.deleted_count == 5

        remaining = await delete_logic(
            email=user.email, artist=None, name=None, source=None, provider=None, purge=True, yes=True
        )
        assert remaining.no_tracks is True

    async def test__nominal__by_provider(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], provider=MusicProvider.SPOTIFY)

        result = await delete_logic(
            email=user.email,
            artist=None,
            name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
            purge=True,
            yes=True,
        )

        assert result.deleted_count == 1
