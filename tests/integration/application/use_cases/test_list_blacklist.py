from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.use_cases.list_blacklist import list_blacklist
from museflow.domain.entities.user import User

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestListBlacklistUseCase:
    async def test__empty(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        result = await list_blacklist(user_id=user.id, blacklist_repository=blacklist_repository)

        assert result.is_empty

    async def test__with_artists_and_tracks(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        result = await list_blacklist(user_id=user.id, blacklist_repository=blacklist_repository)

        assert len(result.artists) == 1
        assert result.artists[0].id == artist_db.id
        assert result.artists[0].artist_name == artist_db.artist_name
        assert len(result.tracks) == 1
        assert result.tracks[0].id == track_db.id
        assert result.tracks[0].name == track_db.name
        assert result.tracks[0].artist_name == track_db.artist_name
