import itertools
import logging
import uuid
from collections.abc import Callable
from collections.abc import Iterator
from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderRateLimitExceededError
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.services.reconciler import Reconciler
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.blacklist import BlacklistedTrackFactory
from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.discovery import ArtistSuggestedFactory
from tests.unit.factories.value_objects.discovery import DiscoveryArtistStrategyFactory
from tests.unit.factories.value_objects.llm import LLMUsageFactory


class TestDiscoverTasteUseCase:
    @pytest.fixture
    def track_roundtrip(self, mock_track_repository: mock.AsyncMock) -> None:
        """No liked tracks, no known track, and bulk_upsert returns the row IDs keyed by fingerprint."""

        async def _bulk_upsert(tracks: list[Track], *, batch_size: int = 100) -> tuple[dict[str, uuid.UUID], int]:
            return {t.fingerprint: t.id for t in tracks}, len(tracks)

        mock_track_repository.get_list.return_value = []
        mock_track_repository.get_covered_artists.return_value = {}
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_track_repository.bulk_upsert.side_effect = _bulk_upsert

    @pytest.fixture
    def pick_all(self, mock_advisor: mock.AsyncMock) -> None:
        """The advisor picks every candidate it is offered, in order, with the same score."""

        async def _pick(candidates: dict[str, list[Track]], **_: object) -> list[TrackPicked]:
            return [TrackPicked(track=track, score=0.9) for tracks in candidates.values() for track in tracks]

        mock_advisor.pick_discovery_tracks.side_effect = _pick

    @pytest.fixture
    def use_case(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        reconciler: Reconciler,
        track_roundtrip: None,
        pick_all: None,
    ) -> DiscoverTasteUseCase:
        mock_blacklist_repository.get.return_value = UserBlacklist()
        mock_playlist_repository.create.side_effect = lambda p: p
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build(user_id=user.id)

        return DiscoverTasteUseCase(
            uow=mock_uow,
            provider_library=mock_provider_library,
            advisor=mock_advisor,
            reconciler=reconciler,
        )

    async def test__profile_loaded_by_name(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
    ) -> None:
        mock_taste_profile_repository.get.return_value = TasteProfileFactory.build(user_id=user.id, name="my-profile")
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        artist = discovery_artist_strategy.artists[0].name
        mock_provider_library.search_artist_tracks.return_value = [TrackFactory.build(artists=[artist])]

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(profile_name="my-profile", playlist_limit=1, dry_run=True),
        )

        mock_taste_profile_repository.get.assert_called_once_with(user_id=user.id, name="my-profile")
        mock_taste_profile_repository.get_latest.assert_not_called()

    async def test__taste_profile_not_found(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = None

        with pytest.raises(TasteProfileNotFoundError):
            await use_case.create_suggestions_playlist(user=user, config=DiscoverTasteConfigInput())

    async def test__taste_profile_status_not_ready(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(
            user_id=user.id, status=TasteProfileStatus.BUILDING
        )

        with pytest.raises(TasteProfileStatusNotReadyError):
            await use_case.create_suggestions_playlist(user=user, config=DiscoverTasteConfigInput())

    @pytest.mark.parametrize("found", [True, False], ids=["all_known", "none_found"])
    async def test__no_candidates__no_new_tracks(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
        found: bool,
    ) -> None:
        """Nothing is offered to pick, and the advisor calls billed are saved."""
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        # The advisor calls billed before the failure.
        mock_advisor.usages = [LLMUsageFactory.build()]
        artist = discovery_artist_strategy.artists[0].name
        mock_provider_library.search_artist_tracks.return_value = (
            [TrackFactory.build(artists=[artist])] if found else []
        )
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=True))

        with pytest.raises(DiscoveryTrackNoNewError):
            await use_case.create_suggestions_playlist(user=user, config=DiscoverTasteConfigInput(max_attempts=1))

        mock_advisor.pick_discovery_tracks.assert_not_awaited()
        # Without any candidate, the library is not even read.
        assert mock_track_repository.get_known_identifiers.await_count == int(found)
        profile = mock_taste_profile_repository.get_latest.return_value
        mock_taste_profile_repository.get.assert_awaited_once_with(user_id=user.id, name=profile.name)
        (record,) = mock_llm_usage_repository.bulk_create.call_args.args[0]
        assert (record.operation, record.playlist_id) == (LLMOperation.DISCOVER, None)

    async def test__search_query_invalid__artist_skipped(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        malformed, valid = ArtistSuggestedFactory.batch(2)
        mock_advisor.get_discovery_artists.return_value = DiscoveryArtistStrategyFactory.build(
            artists=[malformed, valid]
        )
        track = TrackFactory.build(artists=[valid.name])
        mock_provider_library.search_artist_tracks.side_effect = [ProviderSearchQueryInvalidError(), [track]]

        with caplog.at_level(logging.WARNING):
            result = await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoverTasteConfigInput(playlist_limit=1, dry_run=True),
            )

        assert result.tracks == [track]
        assert f"Artist skipped, its search query was rejected: '{malformed.name}'" in caplog.text

    async def test__candidates__filtered(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_blacklist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """Only the unknown, not blacklisted tracks crediting the asked artist are offered, each once."""
        first, second, third = ArtistSuggestedFactory.batch(3)
        mock_advisor.get_discovery_artists.return_value = DiscoveryArtistStrategyFactory.build(
            artists=[first, second, third]
        )

        kept = TrackFactory.build(artists=[first.name])
        close_name = TrackFactory.build(artists=[f"{first.name}lee"])
        blacklisted_artist = TrackFactory.build(artists=[first.name, "A Blacklisted Band"])
        blacklisted_track = TrackFactory.build(artists=[first.name])
        known = TrackFactory.build(artists=[first.name])
        # Credits both artists: offered under the first one only.
        shared = TrackFactory.build(artists=[first.name, second.name])
        only_known = TrackFactory.build(artists=[second.name])
        mock_provider_library.search_artist_tracks.side_effect = [
            [kept, close_name, blacklisted_artist, blacklisted_track, known, shared],
            [shared, only_known],
            # Only an artist with a close name: nothing of the asked one.
            [TrackFactory.build(artists=[f"{third.name} Jr"])],
        ]
        mock_blacklist_repository.get.return_value = UserBlacklist(
            artists=[BlacklistedArtistFactory.build(artist_name="A Blacklisted Band", fingerprint="")],
            tracks=[BlacklistedTrackFactory.build(fingerprint=blacklisted_track.fingerprint)],
        )
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(
            is_known=mock.Mock(side_effect=lambda track: track in (known, only_known))
        )

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=10, max_attempts=1, dry_run=True),
        )

        # The second and third artists are left without any track: not offered at all.
        assert mock_advisor.pick_discovery_tracks.call_args.kwargs["candidates"] == {first.name: [kept, shared]}
        mock_provider_library.search_artist_tracks.assert_any_await(artist=first.name, max_pages=2, log_enabled=False)

    async def test__attempts__artists_and_tracks_not_offered_twice(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """The next attempt excludes the artists already asked, and is not offered the tracks already picked."""
        artist_1, artist_2 = ArtistSuggestedFactory.batch(2)
        mock_advisor.get_discovery_artists.side_effect = [
            DiscoveryArtistStrategyFactory.build(artists=[artist_1]),
            DiscoveryArtistStrategyFactory.build(artists=[artist_2]),
        ]
        picked_1 = TrackFactory.build(artists=[artist_1.name, artist_2.name])
        picked_2 = TrackFactory.build(artists=[artist_2.name])
        mock_provider_library.search_artist_tracks.side_effect = [[picked_1], [picked_1, picked_2]]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=2, max_attempts=3, dry_run=True),
        )

        assert result.tracks == [picked_1, picked_2]
        assert [(r.attempt, r.artists, r.candidates, r.tracks_picked) for r in result.reports] == [
            (1, 1, 1, 1),
            (2, 1, 1, 1),
        ]
        first_call, second_call = mock_advisor.get_discovery_artists.call_args_list
        assert first_call.kwargs["excluded_artists"] is None
        assert second_call.kwargs["excluded_artists"] == [artist_1.name]
        assert mock_advisor.pick_discovery_tracks.call_args.kwargs["candidates"] == {artist_2.name: [picked_2]}

    async def test__tracks__sorted_by_score__capped_per_credited_artist(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
    ) -> None:
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        artist = discovery_artist_strategy.artists[0].name
        low, high, featured, capped = (
            TrackFactory.build(artists=[artist]),
            TrackFactory.build(artists=[artist]),
            TrackFactory.build(artists=["A Guest Band", artist]),
            TrackFactory.build(artists=[artist]),
        )
        mock_provider_library.search_artist_tracks.return_value = [low, high, featured, capped]
        mock_advisor.pick_discovery_tracks.side_effect = None
        mock_advisor.pick_discovery_tracks.return_value = [
            TrackPicked(track=low, score=0.7),
            TrackPicked(track=high, score=0.95),
            TrackPicked(track=featured, score=0.8),
            TrackPicked(track=capped, score=0.75),
        ]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=10, max_attempts=1, max_tracks_per_artist=3, dry_run=True),
        )

        # The featured appearance counts for the artist: the fourth track is over the cap.
        assert result.tracks == [high, featured, capped]

    async def test__remote_calls__run_outside_any_block(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        artists = ArtistSuggestedFactory.batch(2)
        tracks = [TrackFactory.build(artists=[artist.name]) for artist in artists]
        strategies = iter(DiscoveryArtistStrategyFactory.build(artists=[artist]) for artist in artists)
        searches = iter([[track] for track in tracks])
        picks = iter([[TrackPicked(track=track, score=0.9)] for track in tracks])

        # Each remote call records whether a unit of work block was open while it ran.
        blocks_open: list[bool] = []

        def recording(results: Iterator[object]) -> Callable[..., object]:
            def call(**_: object) -> object:
                blocks_open.append(mock_uow.block_open)
                return next(results)

            return call

        mock_advisor.get_discovery_artists.side_effect = recording(strategies)
        mock_provider_library.search_artist_tracks.side_effect = recording(searches)
        mock_advisor.pick_discovery_tracks.side_effect = recording(picks)
        mock_provider_library.create_playlist.side_effect = recording(
            itertools.repeat(PlaylistFactory.build(user_id=user.id))
        )

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=2, max_attempts=2),
        )

        # 2 attempts x (artists + search + picks), then the playlist creation
        assert blocks_open == [False] * 7
        # Initial reads, the known-tracks filter of each attempt, then the final writes
        assert mock_uow.__aenter__.await_count == 4

    async def test__advisor_inputs(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_blacklist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
    ) -> None:
        """The liked and disliked tracks and the blacklist reach the advisor; covered artists are not read at 0."""
        liked_tracks = TrackFactory.batch(2, score=9)
        disliked_tracks = TrackFactory.batch(2, score=1)
        mock_track_repository.get_list.side_effect = [liked_tracks, disliked_tracks]
        mock_blacklist_repository.get.return_value = UserBlacklist(
            artists=[BlacklistedArtistFactory.build(artist_name="A Blacklisted Band")],
            tracks=[BlacklistedTrackFactory.build(name="A Song", artist_name="A Blacklisted Band")],
        )
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        artist = discovery_artist_strategy.artists[0].name
        mock_provider_library.search_artist_tracks.return_value = [TrackFactory.build(artists=[artist])]

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                disliked_tracks_score_threshold=2,
                disliked_tracks_limit=20,
                covered_artists_limit=0,
                dry_run=True,
            ),
        )

        disliked_call_kwargs = mock_track_repository.get_list.call_args_list[1].kwargs
        assert disliked_call_kwargs["max_score"] == 2
        assert disliked_call_kwargs["exclude_skipped"] is True
        assert disliked_call_kwargs["order"] == [(TrackOrderBy.SCORE, SortOrder.ASC)]
        assert disliked_call_kwargs["limit"] == 20
        mock_track_repository.get_covered_artists.assert_not_called()

        advisor_kwargs = mock_advisor.get_discovery_artists.call_args.kwargs
        assert advisor_kwargs["liked_tracks"] == liked_tracks
        assert advisor_kwargs["disliked_tracks"] == disliked_tracks
        assert advisor_kwargs["covered_artists"] is None
        assert advisor_kwargs["blacklisted_artists"] == ["A Blacklisted Band"]
        assert advisor_kwargs["blacklisted_tracks"] == ["A Song by A Blacklisted Band"]

    async def test__remote_playlist_creation_fails__nothing_written(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
    ) -> None:
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        artist = discovery_artist_strategy.artists[0].name
        mock_provider_library.search_artist_tracks.return_value = [TrackFactory.build(artists=[artist])]
        mock_provider_library.create_playlist.side_effect = ProviderRateLimitExceededError("Spotify rate limit")

        with pytest.raises(ProviderRateLimitExceededError):
            await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoverTasteConfigInput(playlist_limit=1, dry_run=False),
            )

        mock_track_repository.bulk_upsert.assert_not_awaited()
        mock_playlist_repository.create.assert_not_awaited()
