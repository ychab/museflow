import logging
from unittest import mock

import pytest

from museflow.application.use_cases.advisor_discover import AdvisorDiscoverUseCase
from museflow.application.use_cases.advisor_discover import DiscoveryConfigInput
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import DiscoveryTrackNoReconciledFound
from museflow.domain.exceptions import DiscoveryTrackNoSeedFound
from museflow.domain.exceptions import DiscoveryTrackNoSimilarFound
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

    async def test__execute__nominal(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Given 2 track seeds
        config = DiscoveryConfigInput(seed_limit=2, similar_limit=2)
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
            playlist = await use_case.create_suggestions_playlist(user=user, config=config)

        # Then check similarity
        assert mock_advisor_client.get_similar_tracks.call_count == len(track_seeds)
        for i, track_seed in enumerate(track_seeds):
            assert f"Track seed: '{track_seed}' => 2 suggestions" in caplog.text, i

        # Then check reconciliation
        assert mock_provider_library.search_tracks.call_count == len(reconciled_tracks)
        assert mock_track_reconciler.reconcile.call_count == len(reconciled_tracks)
        for i, track_suggested in enumerate(tracks_suggested):
            assert f"Track reconciled: '{track_suggested}'" in caplog.text, i

        # Then check known tracks
        assert "New tracks: 1" in caplog.text

        # Then the created playlist
        mock_provider_library.create_playlist.assert_called_once()
        assert playlist == expected_playlist

    async def test_execute__seeds__none(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        with pytest.raises(DiscoveryTrackNoSeedFound):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

    async def test_execute__similar__none(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_advisor_client.get_similar_tracks.return_value = []

        with pytest.raises(DiscoveryTrackNoSimilarFound):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

    async def test_execute__similar__response_exception(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_advisor_client.get_similar_tracks.side_effect = SimilarTrackResponseException("Boom")

        with caplog.at_level(logging.ERROR) and pytest.raises(DiscoveryTrackNoSimilarFound):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

        assert "An error occurred while fetching similar tracks: Boom" in caplog.text

    async def test_execute__reconciled__search_none(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track_seed = TrackFactory.build()
        track_suggested = TrackSuggestedFactory.build()

        mock_track_repository.get_list.return_value = [track_seed]
        mock_advisor_client.get_similar_tracks.return_value = [track_suggested]
        mock_provider_library.search_tracks.return_value = []
        mock_track_reconciler.reconcile.return_value = None

        with caplog.at_level(logging.WARNING), pytest.raises(DiscoveryTrackNoReconciledFound):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

        assert f"Track not reconciled: '{track_suggested}'" in caplog.text

    async def test_execute__reconciled__none(
        self,
        user: User,
        use_case: AdvisorDiscoverUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_advisor_client: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_track_reconciler: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track_seed = TrackFactory.build()
        track_suggested = TrackSuggestedFactory.build()

        mock_track_repository.get_list.return_value = [track_seed]
        mock_advisor_client.get_similar_tracks.return_value = [track_suggested]
        mock_provider_library.search_tracks.return_value = [TrackFactory.build()]
        mock_track_reconciler.reconcile.return_value = None

        with caplog.at_level(logging.WARNING), pytest.raises(DiscoveryTrackNoReconciledFound):
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

        assert f"Track not reconciled: '{track_suggested}'" in caplog.text

    async def test_execute__new_tracks__none(
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
            await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

        assert f"Excluded '{reconciled_track}'" in caplog.text

    async def test_execute__sorting_with_none_score(
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
        await use_case.create_suggestions_playlist(user=user, config=DiscoveryConfigInput())

        # Then
        args, kwargs = mock_provider_library.create_playlist.call_args
        playlist_tracks = kwargs["tracks"]
        assert playlist_tracks[0].name == "High"
        assert playlist_tracks[1].name == "Low"
        assert playlist_tracks[2].name == "None"
