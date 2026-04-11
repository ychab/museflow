from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.discover_taste import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.types import TasteProfiler
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy

from tests.unit.factories.entities.music import PlaylistFactory
from tests.unit.factories.entities.music import TrackArtistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.music import TrackSuggestedFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.value_objects.discovery import DiscoveryTasteStrategyFactory


class TestDiscoverTasteUseCase:
    @pytest.fixture
    def use_case(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> DiscoverTasteUseCase:
        return DiscoverTasteUseCase(
            track_repository=mock_track_repository,
            taste_profile_repository=mock_taste_profile_repository,
            provider_library=mock_provider_library,
            advisor_agent=mock_advisor_agent,
            track_reconciler=mock_track_reconciler,
            profiler=TasteProfiler.GEMINI,
        )

    @pytest.mark.parametrize("discovery_taste_strategy", [{"search_queries": []}], indirect=True)
    async def test__nominal_with_seeds_and_queries(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = (reconciled_track, 0.9)
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))

        playlist = PlaylistFactory.build()
        mock_provider_library.create_playlist.return_value = playlist

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_size=1,
                similar_limit=5,
                dry_run=False,
            ),
        )

        assert result.playlist is playlist
        assert result.strategy is discovery_taste_strategy
        assert len(result.tracks) == 1
        assert len(result.reports) == 1

    async def test__profile_loaded_by_name(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        mock_taste_profile_repository.get.return_value = TasteProfileFactory.build(user_id=user.id, name="my-profile")
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = (reconciled_track, 0.9)
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(profile_name="my-profile", playlist_size=1, similar_limit=5),
        )

        mock_taste_profile_repository.get.assert_called_once_with(user_id=user.id, name="my-profile")
        mock_taste_profile_repository.get_latest.assert_not_called()

    async def test__profile_loaded_as_latest(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = (reconciled_track, 0.9)
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                profile_name=None,
                playlist_size=1,
                similar_limit=5,
            ),
        )

        mock_taste_profile_repository.get_latest.assert_called_once_with(
            user_id=user.id,
            profiler=TasteProfiler.GEMINI,
        )
        mock_taste_profile_repository.get.assert_not_called()

    async def test__taste_profile_not_found(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = None

        with pytest.raises(TasteProfileNotFoundException):
            await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoverTasteConfigInput(),
            )

    async def test__no_new_tracks(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        mock_provider_library.search_tracks.return_value = []
        mock_track_reconciler.reconcile.return_value = None
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=True))

        with pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoverTasteConfigInput(max_attempts=1),
            )

    async def test__dry_run(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = (reconciled_track, 0.9)
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_size=1,
                similar_limit=5,
                dry_run=True,
            ),
        )

        assert result.playlist is None
        mock_provider_library.create_playlist.assert_not_called()

    async def test__search_queries_contribute_tracks(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """Tracks from search_queries path are included with advisor_score=0.8."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        query_track = TrackFactory.build()
        strategy = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[],
            search_queries=["post-rock instrumental"],
        )
        mock_advisor_agent.get_discovery_strategy.return_value = strategy
        mock_provider_library.search_tracks.return_value = [query_track]
        mock_track_reconciler.reconcile.return_value = None
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=1, similar_limit=5),
        )

        assert len(result.tracks) == 1

    async def test__dedup_removes_duplicate_fingerprint(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """The same track returned by both recommended_tracks and search_queries is deduplicated."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        shared_track = TrackFactory.build(isrc=None)

        strategy = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[TrackSuggestedFactory.build(score=1.0)],
            search_queries=["some query"],
        )
        mock_advisor_agent.get_discovery_strategy.return_value = strategy

        # Both paths resolve to the same fingerprint
        mock_track_reconciler.reconcile.return_value = (shared_track, 0.9)
        mock_provider_library.search_tracks.return_value = [shared_track]
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=10, similar_limit=5),
        )

        # Only 1 unique track despite 2 paths
        assert len(result.tracks) == 1

    async def test__dedup_removes_duplicate_isrc(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """The same track returned twice (same ISRC) is deduplicated."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        strategy = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[
                TrackSuggestedFactory.build(score=1.0),
                TrackSuggestedFactory.build(score=0.8),
            ],
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.return_value = strategy

        shared_isrc = "ISRC123"
        mock_track_reconciler.reconcile.side_effect = [
            (TrackFactory.build(isrc=shared_isrc), 0.9),
            (TrackFactory.build(isrc=shared_isrc), 0.8),  # Same ISRC, different object
        ]
        mock_provider_library.search_tracks.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=10, similar_limit=5, max_attempts=1),
        )

        assert len(result.tracks) == 1

    async def test__known_tracks_partially_filtered(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """Known tracks are excluded while unknown ones survive."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        known_track = TrackFactory.build()
        unknown_track = TrackFactory.build()

        strategy = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=TrackSuggestedFactory.batch(2, score=0.9),
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.return_value = strategy

        # First suggestion reconciles to known_track, second to unknown_track
        mock_track_reconciler.reconcile.side_effect = [(known_track, 0.9), (unknown_track, 0.9)]
        mock_provider_library.search_tracks.return_value = [known_track]

        def is_known_side_effect(track: object) -> bool:
            return track is known_track

        mock_track_repository.get_known_identifiers.return_value = mock.Mock(
            is_known=mock.Mock(side_effect=is_known_side_effect)
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=10, similar_limit=5, max_attempts=1, dry_run=False),
        )

        assert all(t is not known_track for t in result.tracks)
        assert len(result.tracks) == 1

    async def test__artist_cap_applied(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        strategy = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=TrackSuggestedFactory.batch(3, score=0.9),  # 3 suggestions for the same artist
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.return_value = strategy

        # All reconcile to tracks with same primary artist
        artist = TrackArtistFactory.build(provider_id="same-artist-id")
        track = TrackFactory.build(artists=[artist])

        mock_track_reconciler.reconcile.side_effect = [
            (track, 0.9),
            (TrackFactory.build(artists=[artist]), 0.9),
            (TrackFactory.build(artists=[artist]), 0.9),
        ]
        mock_provider_library.search_tracks.return_value = [track]
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_size=10,
                similar_limit=5,
                max_attempts=1,
                max_tracks_per_artist=2,
                dry_run=False,
            ),
        )

        # Only 2 tracks from the same artist should survive the cap
        assert len(result.tracks) <= 2

    async def test__loop_stops_early_when_playlist_size_reached(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        discovery_taste_strategy: DiscoveryTasteStrategy,
    ) -> None:
        """Loop exits after the first attempt when playlist_size is already reached."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)
        mock_advisor_agent.get_discovery_strategy.return_value = discovery_taste_strategy

        reconciled_track = TrackFactory.build()
        mock_track_reconciler.reconcile.return_value = (reconciled_track, 0.9)
        mock_provider_library.search_tracks.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=1, similar_limit=5, max_attempts=3),
        )

        mock_advisor_agent.get_discovery_strategy.assert_called_once()
        assert len(result.reports) == 1

    async def test__loop_accumulates_across_attempts(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """Tracks from multiple attempts are merged into the final result."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        track_attempt_1 = TrackFactory.build(isrc="ISRC001")
        track_attempt_2 = TrackFactory.build(isrc="ISRC002")

        strategy_1 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[TrackSuggestedFactory.build(score=0.9)],
            search_queries=[],
        )
        strategy_2 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[TrackSuggestedFactory.build(score=0.9)],
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.side_effect = [strategy_1, strategy_2]
        mock_track_reconciler.reconcile.side_effect = [(track_attempt_1, 0.9), (track_attempt_2, 0.9)]
        mock_provider_library.search_tracks.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=2, similar_limit=5, max_attempts=3),
        )

        assert mock_advisor_agent.get_discovery_strategy.call_count == 2
        assert len(result.tracks) == 2
        assert len(result.reports) == 2

    async def test__excluded_tracks_passed_on_second_attempt(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """On attempt 2+, the advisor receives the tracks suggested in previous attempts as excluded_tracks."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        suggested_track = TrackSuggestedFactory.build(score=0.9)
        track_attempt_1 = TrackFactory.build(isrc="ISRC001")
        track_attempt_2 = TrackFactory.build(isrc="ISRC002")

        strategy_1 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[suggested_track],
            search_queries=[],
        )
        strategy_2 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[TrackSuggestedFactory.build(score=0.9)],
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.side_effect = [strategy_1, strategy_2]
        mock_track_reconciler.reconcile.side_effect = [(track_attempt_1, 0.9), (track_attempt_2, 0.9)]
        mock_provider_library.search_tracks.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=2, similar_limit=5, max_attempts=3),
        )

        # Attempt 1: excluded_tracks=None
        first_call_kwargs = mock_advisor_agent.get_discovery_strategy.call_args_list[0].kwargs
        assert first_call_kwargs["excluded_tracks"] is None

        # Attempt 2: excluded_tracks contains the track suggested in attempt 1
        second_call_kwargs = mock_advisor_agent.get_discovery_strategy.call_args_list[1].kwargs
        assert second_call_kwargs["excluded_tracks"] == [suggested_track]

    async def test__excluded_tracks_capped_at_50(
        self,
        user: User,
        use_case: DiscoverTasteUseCase,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_advisor_agent: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        """The excluded_tracks list passed to the advisor is capped at 50 entries."""
        mock_taste_profile_repository.get_latest.return_value = TasteProfileFactory.build(user_id=user.id)

        # 60 suggested tracks in attempt 1 — more than the cap of 50
        many_suggestions = TrackSuggestedFactory.batch(60, score=0.9)
        strategy_1 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=many_suggestions,
            search_queries=[],
        )
        strategy_2 = DiscoveryTasteStrategyFactory.build(
            recommended_tracks=[TrackSuggestedFactory.build(score=0.9)],
            search_queries=[],
        )
        mock_advisor_agent.get_discovery_strategy.side_effect = [strategy_1, strategy_2]

        # Attempt 1: all 60 suggestions fail to reconcile → 0 new tracks → loop continues
        # Attempt 2: produces 1 new track → loop stops
        new_track = TrackFactory.build(isrc="ISRC_NEW")
        mock_track_reconciler.reconcile.side_effect = [None] * 60 + [(new_track, 0.9)]
        mock_provider_library.search_tracks.return_value = []
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_size=1, similar_limit=60, max_attempts=2),
        )

        second_call_kwargs = mock_advisor_agent.get_discovery_strategy.call_args_list[1].kwargs
        excluded = second_call_kwargs["excluded_tracks"]
        assert excluded is not None
        assert len(excluded) == 50
