import logging
from collections.abc import Callable
from dataclasses import replace
from unittest import mock

import pytest

from museflow.application.inputs.explore import CreateExplorationPlaylistConfigInput
from museflow.application.outputs.progress import CandidatesFound
from museflow.application.outputs.progress import PicksMade
from museflow.application.outputs.progress import StepStarted
from museflow.application.use_cases.playlist_exploration_create import CreateExplorationPlaylistUseCase
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import ProgressStep
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.taste import ArtistSearch
from museflow.domain.value_objects.taste import TrackPicked

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.outputs.stats import ArtistStatsFactory
from tests.unit.factories.value_objects.llm import LLMUsageFactory


class TestCreateExplorationPlaylistUseCase:
    @pytest.fixture
    def use_case(
        self,
        mock_uow: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
    ) -> CreateExplorationPlaylistUseCase:
        """No liked track, nothing known, and the advisor picks every candidate it is offered, in order."""

        async def _pick(candidates: dict[str, list[Track]], **_: object) -> list[TrackPicked]:
            return [TrackPicked(track=track, score=0.9) for tracks in candidates.values() for track in tracks]

        mock_blacklist_repository.get.return_value = UserBlacklist()
        mock_track_repository.get_list.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.search_artist_catalogue.side_effect = lambda artist, **_: [
            TrackFactory.build(artists=[artist])
        ]
        mock_advisor.pick_exploration_tracks.side_effect = _pick
        return CreateExplorationPlaylistUseCase(
            uow=mock_uow, provider_library=mock_provider_library, advisor=mock_advisor, progress=mock_progress
        )

    async def test__artists__drawn__catalogue_searched__capped(
        self,
        user: User,
        use_case: CreateExplorationPlaylistUseCase,
        mock_blacklist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """The best favourites not blacklisted are searched deep, the advisor sees what the user loves in them."""
        mock_track_repository.get_artist_stats.return_value = [
            ArtistStatsFactory.build(artist="Most Played", plays_count=30),
            ArtistStatsFactory.build(artist="A Blacklisted Band", plays_count=20),
            ArtistStatsFactory.build(artist="Played", plays_count=10),
            ArtistStatsFactory.build(artist="Least Played", plays_count=5),
        ]
        mock_blacklist_repository.get.return_value = UserBlacklist(
            artists=[BlacklistedArtistFactory.build(artist_name="A Blacklisted Band")],
        )
        liked_most_played = TrackFactory.batch(6, artists=["Most Played"], score=9)
        mock_track_repository.get_list.return_value = [*liked_most_played, TrackFactory.build(artists=["Someone"])]
        tracks_most_played = TrackFactory.batch(2, artists=["Most Played"])
        track_played = TrackFactory.build(artists=["Played"])
        mock_provider_library.search_artist_catalogue.side_effect = lambda artist, **_: {
            "Most Played": tracks_most_played,
            "Played": [track_played],
        }[artist]

        result = await use_case.create_playlist(
            user=user,
            config=CreateExplorationPlaylistConfigInput(
                artists_limit=2,
                artists_per_attempt=2,
                picks_limit=7,
                catalogue_tracks_pages=5,
                max_tracks_per_artist=1,
                max_attempts=1,
                dry_run=True,
            ),
        )

        calls = mock_provider_library.search_artist_catalogue.await_args_list
        assert sorted((call.kwargs["artist"], call.kwargs["max_pages"]) for call in calls) == [
            ("Most Played", 5),
            ("Played", 5),
        ]
        mock_provider_library.search_artist_tracks.assert_not_called()
        picks_kwargs = mock_advisor.pick_exploration_tracks.call_args.kwargs
        assert (picks_kwargs["tracks_limit"], picks_kwargs["max_tracks_per_artist"]) == (7, 1)
        # The liked tracks of each candidate artist, at most 5: "Played" has none.
        assert picks_kwargs["liked_tracks"] == {"Most Played": liked_most_played[:5]}
        assert sorted(result.tracks, key=lambda track: track.artists[0]) == [tracks_most_played[0], track_played]

    async def test__attempts__no_artist_left__stops(
        self,
        user: User,
        use_case: CreateExplorationPlaylistUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each round takes the next favourites; once none is left, the run ends short of the limit."""
        mock_track_repository.get_artist_stats.return_value = ArtistStatsFactory.batch(2)

        with caplog.at_level(logging.DEBUG):
            result = await use_case.create_playlist(
                user=user,
                config=CreateExplorationPlaylistConfigInput(
                    artists_per_attempt=1, playlist_limit=10, max_attempts=3, dry_run=True
                ),
            )

        # Each round announced, then its outcome; no artists step (they come from the user's data), and a dry run
        # creates no playlist.
        events = [call.args[0] for call in mock_progress.publish.await_args_list]
        track_1, track_2 = (pick.track for event in events if isinstance(event, PicksMade) for pick in event.picks)
        artist_1, artist_2 = (track.artists[0] for track in (track_1, track_2))
        assert events == [
            StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1, max_attempts=3),
            CandidatesFound(attempt=1, searches=[ArtistSearch(artist=artist_1, found=1, matched=1, tracks=[track_1])]),
            StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1),
            PicksMade(attempt=1, picks=[TrackPicked(track=track_1, score=0.9)], tracks=[track_1], target=10),
            StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=2, max_attempts=3),
            CandidatesFound(attempt=2, searches=[ArtistSearch(artist=artist_2, found=1, matched=1, tracks=[track_2])]),
            StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=2),
            PicksMade(attempt=2, picks=[TrackPicked(track=track_2, score=0.9)], tracks=[track_1, track_2], target=10),
        ]
        assert mock_advisor.pick_exploration_tracks.await_count == 2
        assert len({track.artists[0] for track in result.tracks}) == 2
        assert "Attempt 3/3: no favourite artist left, stopping" in caplog.text
        assert "playlist_limit not reached (2/10) after 2 attempt(s)" in caplog.text

    async def test__no_favourite_artist__no_new_tracks(
        self,
        user: User,
        use_case: CreateExplorationPlaylistUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_stats.return_value = []

        with pytest.raises(DiscoveryTrackNoNewError):
            await use_case.create_playlist(user=user, config=CreateExplorationPlaylistConfigInput())

        mock_advisor.pick_exploration_tracks.assert_not_called()

    async def test__all_known__no_new_tracks__usage_recorded(
        self,
        user: User,
        use_case: CreateExplorationPlaylistUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
    ) -> None:
        """Nothing new to pick ends the run, and the advisor calls billed before are saved."""
        mock_track_repository.get_artist_stats.return_value = ArtistStatsFactory.batch(1)
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=True))
        mock_advisor.pop_usages.return_value = [LLMUsageFactory.build()]

        with pytest.raises(DiscoveryTrackNoNewError):
            await use_case.create_playlist(user=user, config=CreateExplorationPlaylistConfigInput(max_attempts=1))

        mock_advisor.pick_exploration_tracks.assert_not_awaited()
        (record,) = mock_llm_usage_repository.bulk_accumulate.call_args.args[0]
        assert (record.operation, record.profile_id, record.playlist_id) == (LLMOperation.EXPLORE, None, None)

    async def test__remote_calls__run_outside_any_block(
        self,
        user: User,
        use_case: CreateExplorationPlaylistUseCase,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        artist = "The Fictional Band"
        track = TrackFactory.build(artists=[artist])
        mock_track_repository.get_artist_stats.return_value = [ArtistStatsFactory.build(artist=artist)]
        mock_track_repository.bulk_upsert.return_value = ({track.fingerprint: track.id}, 1)
        mock_playlist_repository.create.side_effect = lambda playlist: playlist

        # Each remote call records whether a unit of work block was open while it ran.
        blocks_open: list[bool] = []

        def recording(result: object) -> Callable[..., object]:
            def call(**_: object) -> object:
                blocks_open.append(mock_uow.block_open)
                return result

            return call

        mock_provider_library.search_artist_catalogue.side_effect = recording([track])
        mock_advisor.pick_exploration_tracks.side_effect = recording([TrackPicked(track=track, score=0.9)])
        mock_provider_library.create_playlist.side_effect = recording(PlaylistFactory.build(user_id=user.id))

        result = await use_case.create_playlist(
            user=user, config=CreateExplorationPlaylistConfigInput(playlist_limit=1)
        )

        # The search, the picks, then the playlist creation
        assert blocks_open == [False] * 3
        # Initial reads, the known-tracks filter, then the final writes
        assert mock_uow.__aenter__.await_count == 3
        assert result.playlist is not None
        # Saved as discoveries, so that the next runs exclude them
        assert result.tracks == [replace(track, source=TrackSource.DISCOVERY)]
