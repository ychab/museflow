import logging
from unittest import mock

import pytest

from museflow.application.use_cases.advisor_discover import AdvisorDiscoverUseCase
from museflow.application.use_cases.advisor_discover import DiscoveryAttemptReport
from museflow.application.use_cases.advisor_discover import DiscoveryConfigInput
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.domain.value_objects.music import TrackKnowIdentifiers

from tests.unit.factories.entities.music import PlaylistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.music import TrackSuggestedFactory


class TestAdvisorDiscoverTracksUseCase:
    @pytest.fixture
    def use_case(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> AdvisorDiscoverUseCase:
        return AdvisorDiscoverUseCase(
            track_repository=mock_track_repository,
            provider_library=mock_provider_library,
            advisor_client=mock_advisor_client,
            track_reconciler=mock_track_reconciler,
        )

    async def test__nominal(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Given 2 track seeds — playlist_size=1 ensures the loop stops after attempt 1
        config = DiscoveryConfigInput(seed_limit=2, similar_limit=2, playlist_size=1, max_attempts=3)
        track_seeds = TrackFactory.batch(size=2)
        mock_track_repository.get_list.return_value = track_seeds

        # Given 2 similarities for EACH track seed
        tracks_suggested = [
            TrackSuggestedFactory.build(score=0.9),
            TrackSuggestedFactory.build(score=0.8),
        ]
        mock_advisor_client.get_similar_tracks.return_value = tracks_suggested
        mock_advisor_client.display_name = "Last.fm"

        # Given reconciled with one reconciled track for EACH suggestion
        reconciled_tracks = TrackFactory.batch(size=len(track_seeds) * len(tracks_suggested))
        mock_provider_library.search_tracks.side_effect = [[t] for t in reconciled_tracks]
        mock_track_reconciler.reconcile.side_effect = [t for t in reconciled_tracks]

        # Given known tracks: 3 tracks are already known, one is new
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(t.isrc for t in reconciled_tracks[1:] if t.isrc),
            fingerprints=frozenset(t.fingerprint for t in reconciled_tracks[1:]),
        )

        expected_playlist = PlaylistFactory.build(tracks=[reconciled_tracks[0]])
        mock_provider_library.create_playlist.return_value = expected_playlist

        # When
        with caplog.at_level(logging.INFO):
            playlist, reports = await use_case.create_suggestions_playlist(user=user, config=config)

        # Then check similarity
        assert mock_advisor_client.get_similar_tracks.call_count == len(track_seeds)
        for i, track_seed in enumerate(track_seeds):
            assert f"Track seed: '{track_seed}' => 2 suggestions" in caplog.text, i

        # Then check reconciliation
        assert mock_provider_library.search_tracks.call_count == len(reconciled_tracks)
        assert mock_track_reconciler.reconcile.call_count == len(reconciled_tracks)
        for i, track_suggested in enumerate(tracks_suggested):
            assert f"Track reconciled: '{track_suggested}'" in caplog.text, i

        # Then check the attempt log
        assert "Attempt 1/3: +1 tracks (total: 1)" in caplog.text

        # Then the created playlist
        mock_provider_library.create_playlist.assert_called_once()
        assert playlist == expected_playlist

        # Then check the report
        assert len(reports) == 1
        assert reports[0] == DiscoveryAttemptReport(
            attempt=1,
            tracks_seeds=2,
            tracks_suggested=4,
            tracks_reconciled=4,
            tracks_survived=1,
            tracks_new=1,
        )

    async def test__no_seeds__raises(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        with pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput(max_attempts=1))

    async def test__similar__none__raises(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_advisor_client.get_similar_tracks.return_value = []

        with caplog.at_level(logging.WARNING), pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput(max_attempts=1))

        assert "Attempt 1: no similar tracks found, continuing..." in caplog.text

    async def test__similar__response_exception(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_advisor_client.get_similar_tracks.side_effect = SimilarTrackResponseException("Boom")

        with caplog.at_level(logging.ERROR), pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput(max_attempts=1))

        assert "An error occurred while fetching similar tracks: Boom" in caplog.text

    async def test__reconciled__none__raises(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track_suggested = TrackSuggestedFactory.build()
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        mock_advisor_client.get_similar_tracks.return_value = [track_suggested]
        mock_provider_library.search_tracks.return_value = [TrackFactory.build()]
        mock_track_reconciler.reconcile.return_value = None

        with caplog.at_level(logging.WARNING), pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput(max_attempts=1))

        assert f"Track not reconciled: '{track_suggested}'" in caplog.text
        assert "Attempt 1: no reconciled tracks found, continuing..." in caplog.text

    async def test__new_tracks__none__raises(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_advisor_client.get_similar_tracks.return_value = [TrackSuggestedFactory.build()]

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = reconciled_track

        # All tracks are already known
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset([reconciled_track.isrc] if reconciled_track.isrc else []),
            fingerprints=frozenset([reconciled_track.fingerprint]),
        )

        with caplog.at_level(logging.INFO), pytest.raises(DiscoveryTrackNoNew):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput(max_attempts=1))

        assert f"Excluded '{reconciled_track}'" in caplog.text

    async def test__reached_on_second_attempt(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        # Given: playlist_size=2, each attempt contributes 1 new track
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        mock_advisor_client.get_similar_tracks.side_effect = [
            [TrackSuggestedFactory.build(score=0.9)],
            [TrackSuggestedFactory.build(score=0.8)],
        ]

        track_1 = TrackFactory.build()
        track_2 = TrackFactory.build()
        mock_provider_library.search_tracks.side_effect = [[track_1], [track_2]]
        mock_track_reconciler.reconcile.side_effect = [track_1, track_2]

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        _, reports = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoveryConfigInput(
                seed_limit=1,
                similar_limit=1,
                playlist_size=2,
                max_attempts=3,
            ),
        )

        # Then: loop ran exactly 2 attempts (not 3)
        assert mock_track_repository.get_list.call_count == 2
        assert len(mock_provider_library.create_playlist.call_args.kwargs["tracks"]) == 2
        assert len(reports) == 2

    async def test__partial_after_max_attempts(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Given: playlist_size=5 but only 2 tracks total across max_attempts=2
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        mock_advisor_client.get_similar_tracks.side_effect = [
            [TrackSuggestedFactory.build(score=0.9)],
            [TrackSuggestedFactory.build(score=0.8)],
        ]

        track_1 = TrackFactory.build()
        track_2 = TrackFactory.build()
        mock_provider_library.search_tracks.side_effect = [[track_1], [track_2]]
        mock_track_reconciler.reconcile.side_effect = [track_1, track_2]

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        with caplog.at_level(logging.WARNING):
            _, reports = await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoveryConfigInput(
                    seed_limit=1,
                    similar_limit=1,
                    playlist_size=5,
                    max_attempts=2,
                ),
            )

        # Then: partial playlist created with warning
        assert "playlist_size not reached (2/5) after 2 attempt(s)" in caplog.text
        mock_provider_library.create_playlist.assert_called_once()
        assert len(mock_provider_library.create_playlist.call_args.kwargs["tracks"]) == 2
        assert len(reports) == 2

    async def test__seeds_exhausted_mid_loop(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Given: DB runs dry on attempt 2
        mock_track_repository.get_list.side_effect = [[TrackFactory.build()], []]
        mock_advisor_client.get_similar_tracks.return_value = [TrackSuggestedFactory.build(score=0.9)]

        track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [track]
        mock_track_reconciler.reconcile.return_value = track

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        with caplog.at_level(logging.INFO):
            _, reports = await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoveryConfigInput(
                    seed_limit=1,
                    similar_limit=1,
                    playlist_size=5,
                    max_attempts=5,
                ),
            )

        # Then: stopped after 2nd call (empty seeds), partial playlist created
        assert mock_track_repository.get_list.call_count == 2
        assert "Seeds exhausted, stopping." in caplog.text
        assert "playlist_size not reached (1/5) after 5 attempt(s)" in caplog.text
        assert len(reports) == 2
        assert reports[1] == DiscoveryAttemptReport(attempt=2)

    async def test__inter_iteration_dedup(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        # Given: same track suggested in both attempts
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        mock_advisor_client.get_similar_tracks.return_value = [TrackSuggestedFactory.build(score=0.9)]

        track_1 = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [track_1]
        mock_track_reconciler.reconcile.return_value = track_1

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        _, reports = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoveryConfigInput(
                seed_limit=1,
                similar_limit=1,
                playlist_size=5,
                max_attempts=2,
            ),
        )

        # Then: track_a appears only once in the playlist despite being in both attempts
        assert len(mock_provider_library.create_playlist.call_args.kwargs["tracks"]) == 1
        assert mock_provider_library.create_playlist.call_args.kwargs["tracks"][0] == track_1
        assert len(reports) == 2

    async def test__trim_by_score(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        # Given: 3 tracks found but playlist_size=2 → lowest score trimmed
        mock_track_repository.get_list.return_value = [TrackFactory.build()]

        suggestions = [
            TrackSuggestedFactory.build(name="High", score=0.9),
            TrackSuggestedFactory.build(name="Mid", score=0.5),
            TrackSuggestedFactory.build(name="Low", score=0.1),
        ]
        mock_advisor_client.get_similar_tracks.return_value = suggestions

        reconciled = {s.name: TrackFactory.build(name=s.name) for s in suggestions}
        mock_provider_library.search_tracks.side_effect = lambda track, **kwargs: [reconciled[track]]
        mock_track_reconciler.reconcile.side_effect = lambda track_suggested, candidates: candidates[0]

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        _, reports = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoveryConfigInput(
                seed_limit=1,
                similar_limit=3,
                playlist_size=2,
                max_attempts=1,
            ),
        )

        # Then: only the top-2 by score are in the playlist
        _, kwargs = mock_provider_library.create_playlist.call_args
        playlist_tracks = kwargs["tracks"]
        assert len(playlist_tracks) == 2
        assert playlist_tracks[0].name == "High"
        assert playlist_tracks[1].name == "Mid"
        assert len(reports) == 1

    async def test__dry_run(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        mock_advisor_client.get_similar_tracks.return_value = [TrackSuggestedFactory.build(score=0.9)]

        reconciled_track = TrackFactory.build()
        mock_provider_library.search_tracks.return_value = [reconciled_track]
        mock_track_reconciler.reconcile.return_value = reconciled_track

        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset(),
        )

        with caplog.at_level(logging.INFO):
            result, reports = await use_case.create_suggestions_playlist(
                user=user,
                config=DiscoveryConfigInput(seed_limit=1, max_attempts=1, dry_run=True),
            )

        assert result is None
        assert len(reports) == 1
        mock_provider_library.create_playlist.assert_not_called()
        assert "Dry-run mode: skipping playlist creation." in caplog.text

    async def test__sorting_with_none_score(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
    ) -> None:
        # Given one seed
        mock_track_repository.get_list.return_value = [TrackFactory.build()]

        # Given 3 suggested tracks with one NULL score
        suggestions = [
            TrackSuggestedFactory.build(name="Low", score=0.1),
            TrackSuggestedFactory.build(name="None", score=None),
            TrackSuggestedFactory.build(name="High", score=0.9),
        ]
        mock_advisor_client.get_similar_tracks.return_value = suggestions
        mock_advisor_client.display_name = "Last.fm"

        # Given a reconciled track for each track suggested
        reconciled_tracks = {t.name: TrackFactory.build(name=t.name) for t in suggestions}
        mock_provider_library.search_tracks.side_effect = lambda track, **kwargs: [reconciled_tracks.get(track)]
        mock_track_reconciler.reconcile.side_effect = lambda track_suggested, candidates: candidates[0]

        # Given new tracks for each reconciled track with a new playlist created
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            isrcs=frozenset(), fingerprints=frozenset()
        )
        mock_provider_library.create_playlist.return_value = PlaylistFactory.build()

        # When
        _, reports = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoveryConfigInput(
                playlist_size=3,
                max_attempts=1,
            ),
        )

        # Then: tracks sorted by score DESC (None treated as 0)
        playlist_tracks = mock_provider_library.create_playlist.call_args.kwargs["tracks"]
        assert playlist_tracks[0].name == "High"
        assert playlist_tracks[1].name == "Low"
        assert playlist_tracks[2].name == "None"
        assert len(reports) == 1
