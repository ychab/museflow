from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.use_cases.playlist_history import playlist_history
from museflow.domain.entities.user import User
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import PlaylistHistoryOrderBy
from museflow.domain.enums import TrackSource

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

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [high.id, mid.id, low.id]

    async def test__dry_run__no_playlist_persisted(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        high = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=10)
        low = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=1)

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=20, dry_run=True),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is None
        assert [t.id for t in result.tracks] == [high.id, low.id]
        assert await playlist_repository.list(user.id) == []

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

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(score_min=5, artist_name="Matching Artist", limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [matching.id]

    async def test__dedup_excludes_tracks_from_previous_history_playlist(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=10)
        second = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, played_count=5)

        first_result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=1),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )
        assert first_result.playlist is not None
        assert len(first_result.playlist.tracks) == 1

        second_result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert second_result.playlist is not None
        assert [t.id for t in second_result.playlist.tracks] == [second.id]

    async def test__sort_by_score__ordered_correctly(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        low = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=3)
        high = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=9)
        mid = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=6)
        unscored = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=None)

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(sort_by=PlaylistHistoryOrderBy.SCORE, limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [high.id, mid.id, low.id, unscored.id]

    async def test__filters_by_played_first_range(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        inside = await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_first=datetime(2025, 6, 15, tzinfo=UTC),
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_first=datetime(2024, 3, 1, tzinfo=UTC),
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_first=None,
        )

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(
                played_first_min=date(2025, 1, 1),
                played_first_max=date(2025, 12, 31),
                limit=20,
            ),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [inside.id]

    async def test__filters_by_played_last_range(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        inside = await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_last=datetime(2026, 7, 20, tzinfo=UTC),
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_last=datetime(2025, 11, 5, tzinfo=UTC),
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            source=TrackSource.HISTORY,
            played_at_last=None,
        )

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(
                played_last_min=date(2026, 6, 21),
                played_last_max=date(2026, 9, 22),
                limit=20,
            ),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [inside.id]

    async def test__filters_by_genre(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        matching = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, genres=[GenreTag.HIP_HOP.value]
        )
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, genres=[GenreTag.ROCK.value])

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(genres=[GenreTag.HIP_HOP], limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [matching.id]

    async def test__filters_by_mood(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        matching = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, moods=[MoodTag.CHILL.value]
        )
        await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, moods=[MoodTag.ENERGETIC.value]
        )

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(moods=[MoodTag.CHILL], limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [matching.id]

    async def test__filters_by_locale(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        matching = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, locale="fr")
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, locale="en")

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(locales=["fr"], limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert [t.id for t in result.playlist.tracks] == [matching.id]

    async def test__filters_by_multiple_locales__or_logic(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        fr = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, locale="fr")
        en = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, locale="en")
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, locale="de")

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(locales=["fr", "en"], limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert {t.id for t in result.playlist.tracks} == {fr.id, en.id}

    async def test__filters_by_multiple_genres__or_logic(
        self,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        hip_hop = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, genres=[GenreTag.HIP_HOP.value]
        )
        rock = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, genres=[GenreTag.ROCK.value]
        )
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, genres=[GenreTag.JAZZ.value])

        result = await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(genres=[GenreTag.HIP_HOP, GenreTag.ROCK], limit=20),
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=spotify_library,
        )

        assert result.playlist is not None
        assert {t.id for t in result.playlist.tracks} == {hip_hop.id, rock.id}
