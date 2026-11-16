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
from museflow.domain.enums import ProgressStep
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.progress import PicksMade
from museflow.domain.value_objects.progress import StepStarted
from museflow.domain.value_objects.progress import StrategyChosen
from museflow.domain.value_objects.taste import ArtistSearch
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
        mock_progress: mock.AsyncMock,
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
            progress=mock_progress,
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

    async def test__attempts__artists_and_tracks_not_offered_twice(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
    ) -> None:
        """The next attempt excludes the artists already asked, and is not offered the tracks already picked."""
        artist_1, artist_2 = ArtistSuggestedFactory.batch(2)
        strategy_1 = DiscoveryArtistStrategyFactory.build(artists=[artist_1])
        strategy_2 = DiscoveryArtistStrategyFactory.build(artists=[artist_2])
        mock_advisor.get_discovery_artists.side_effect = [strategy_1, strategy_2]
        picked_1 = TrackFactory.build(artists=[artist_1.name, artist_2.name])
        picked_2 = TrackFactory.build(artists=[artist_2.name])
        mock_provider_library.search_artist_tracks.side_effect = [[picked_1], [picked_1, picked_2]]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=2, max_attempts=3, dry_run=True),
        )

        assert result.tracks == [picked_1, picked_2]
        # Each step announced, then its outcome; a dry run creates no playlist.
        assert [call.args[0] for call in mock_progress.publish.await_args_list] == [
            StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=1, max_attempts=3),
            StrategyChosen(attempt=1, strategy=strategy_1),
            StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1),
            CandidatesFound(
                attempt=1, searches=[ArtistSearch(artist=artist_1.name, found=1, matched=1, tracks=[picked_1])]
            ),
            StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1),
            PicksMade(attempt=1, picks=[TrackPicked(track=picked_1, score=0.9)], tracks=[picked_1], target=2),
            StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=2, max_attempts=3),
            StrategyChosen(attempt=2, strategy=strategy_2),
            StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=2),
            # The track picked earlier is not offered again
            CandidatesFound(
                attempt=2, searches=[ArtistSearch(artist=artist_2.name, found=2, matched=2, tracks=[picked_2])]
            ),
            StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=2),
            PicksMade(
                attempt=2, picks=[TrackPicked(track=picked_2, score=0.9)], tracks=[picked_1, picked_2], target=2
            ),
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

    async def test__requested_artist__catalogue_searched__uncapped(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """The artist whose own tracks the request asks for gets a catalogue search, and neither limits nor counts."""
        requested = ArtistSuggestedFactory.build(requested=True)
        other = ArtistSuggestedFactory.build()
        mock_advisor.get_discovery_artists.return_value = DiscoveryArtistStrategyFactory.build(
            artists=[requested, other]
        )
        tracks_requested = TrackFactory.batch(3, artists=[requested.name])
        # Counts for the other artist only: the requested one is not capped.
        featuring = TrackFactory.build(artists=[requested.name, other.name])
        track_other = TrackFactory.build(artists=[other.name])
        mock_provider_library.search_artist_catalogue.return_value = [*tracks_requested, featuring]
        mock_provider_library.search_artist_tracks.return_value = [track_other]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=10,
                max_attempts=1,
                max_tracks_per_artist=1,
                artist_tracks_pages=2,
                requested_artist_tracks_pages=5,
                dry_run=True,
            ),
        )

        assert result.tracks == [*tracks_requested, featuring]
        mock_provider_library.search_artist_catalogue.assert_awaited_once_with(artist=requested.name, max_pages=5)
        mock_provider_library.search_artist_tracks.assert_awaited_once_with(artist=other.name, max_pages=2)

    async def test__attempts__only_requested_artists__stops(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """A request naming only artists has no other artist to ask for: no further paid attempt."""
        requested = ArtistSuggestedFactory.build(requested=True)
        mock_advisor.get_discovery_artists.return_value = DiscoveryArtistStrategyFactory.build(artists=[requested])
        track = TrackFactory.build(artists=[requested.name])
        mock_provider_library.search_artist_catalogue.return_value = [track]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=10, max_attempts=3, dry_run=True),
        )

        mock_advisor.get_discovery_artists.assert_awaited_once()
        assert result.tracks == [track]

    async def test__attempts__no_artist_left__stops(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
    ) -> None:
        """An attempt suggesting no artist ends the run: the next ones would be paid for nothing."""
        artist = ArtistSuggestedFactory.build()
        strategy = DiscoveryArtistStrategyFactory.build(artists=[artist])
        mock_advisor.get_discovery_artists.side_effect = [
            strategy,
            DiscoveryArtistStrategyFactory.build(artists=[]),
        ]
        track = TrackFactory.build(artists=[artist.name])
        mock_provider_library.search_artist_tracks.return_value = [track]

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=10, max_attempts=3, dry_run=True),
        )

        assert mock_advisor.get_discovery_artists.await_count == 2
        mock_advisor.pick_discovery_tracks.assert_awaited_once()
        # The strategy that chose the tracks is kept.
        assert result.strategy == strategy
        assert result.tracks == [track]
        picks = [call.args[0] for call in mock_progress.publish.await_args_list if isinstance(call.args[0], PicksMade)]
        assert [event.attempt for event in picks] == [1]

    async def test__attempts__capped_below_limit__next_attempt(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An attempt reaching the limit before the per-artist cap, but not after it, is followed by another one."""
        artist_1, artist_2 = ArtistSuggestedFactory.batch(2)
        mock_advisor.get_discovery_artists.side_effect = [
            DiscoveryArtistStrategyFactory.build(artists=[artist_1]),
            DiscoveryArtistStrategyFactory.build(artists=[artist_2]),
        ]
        tracks_1 = TrackFactory.batch(3, artists=[artist_1.name])
        track_2 = TrackFactory.build(artists=[artist_2.name])
        mock_provider_library.search_artist_tracks.side_effect = [tracks_1, [track_2]]

        with caplog.at_level(logging.INFO):
            result = await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoverTasteConfigInput(
                    playlist_limit=3, max_attempts=2, max_tracks_per_artist=1, dry_run=True
                ),
            )

        assert result.tracks == [tracks_1[0], track_2]
        picks = [call.args[0] for call in mock_progress.publish.await_args_list if isinstance(call.args[0], PicksMade)]
        assert [(len(event.picks), len(event.tracks)) for event in picks] == [(3, 1), (1, 2)]
        assert "playlist_limit not reached (2/3) after 2 attempt(s)" in caplog.text

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
        # The third read is the known-tracks catch, by title: nothing in the library.
        mock_track_repository.get_list.side_effect = [liked_tracks, disliked_tracks, []]
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

    async def test__advisor_inputs__covered_artists(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        discovery_artist_strategy: DiscoveryArtistStrategy,
    ) -> None:
        covered_artists = {"The Fictional Band": 3, "Another Band": 2}
        mock_track_repository.get_covered_artists.return_value = covered_artists
        mock_advisor.get_discovery_artists.return_value = discovery_artist_strategy
        artist = discovery_artist_strategy.artists[0].name
        mock_provider_library.search_artist_tracks.return_value = [TrackFactory.build(artists=[artist])]

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=1, covered_artists_limit=2, dry_run=True),
        )

        mock_track_repository.get_covered_artists.assert_called_once_with(user_id=user.id, limit=2)
        assert mock_advisor.get_discovery_artists.call_args.kwargs["covered_artists"] == covered_artists
