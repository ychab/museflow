import pytest

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.use_cases.playlist_history import playlist_history
from museflow.domain.entities.user import User
from museflow.domain.types import TrackSource

from tests.integration.factories.models.track import TrackModelFactory


@pytest.mark.wiremock("spotify")
class TestPlaylistHistoryUseCase:
    async def test__nominal__ordered_by_played_count(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        low = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=1)
        high = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=10)
        mid = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=5)

        playlist = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert [t.id for t in playlist.tracks] == [high.id, mid.id, low.id]

    async def test__filters_by_score_and_artist(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        matching = await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            score=8,
            artists=["Matching Artist"],
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            score=2,
            artists=["Matching Artist"],
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            score=9,
            artists=["Other Artist"],
        )

        playlist = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(score_min=5, artist_name="Matching Artist", limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert [t.id for t in playlist.tracks] == [matching.id]

    async def test__dedup_excludes_tracks_from_previous_history_playlist(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=10)
        second = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=5)

        first_playlist = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=1),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )
        assert len(first_playlist.tracks) == 1

        second_playlist = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert [t.id for t in second_playlist.tracks] == [second.id]
