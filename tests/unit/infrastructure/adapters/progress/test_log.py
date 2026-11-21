import logging
from collections.abc import Iterator
from unittest import mock

import pytest

from museflow.application.outputs.progress import CandidatesFound
from museflow.application.outputs.progress import PicksMade
from museflow.application.outputs.progress import PlaylistCreated
from museflow.application.outputs.progress import ProgressEvent
from museflow.application.outputs.progress import StepAdvanced
from museflow.application.outputs.progress import StepDone
from museflow.application.outputs.progress import StepResumed
from museflow.application.outputs.progress import StepStarted
from museflow.application.outputs.progress import StrategyChosen
from museflow.domain.enums import ProgressStep
from museflow.domain.value_objects.taste import ArtistSearch
from museflow.domain.value_objects.taste import TrackPicked
from museflow.infrastructure.adapters.progress.log import LogProgressAdapter

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.discovery import ArtistSuggestedFactory
from tests.unit.factories.value_objects.discovery import DiscoveryArtistStrategyFactory


class TestLogProgressAdapter:
    @pytest.fixture
    def adapter(self) -> LogProgressAdapter:
        return LogProgressAdapter()

    @pytest.mark.parametrize(
        ("event", "message"),
        [
            (
                StepStarted(step=ProgressStep.ENRICH_TRACKS, total=400),
                "Step enrich_tracks started (400 units)",
            ),
            (
                StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=2, max_attempts=3),
                "Step discovery_artists started, attempt 2",
            ),
            (
                StepResumed(step=ProgressStep.ENRICH_TRACKS, done=200, total=400),
                "Step enrich_tracks resumed at 200/400 from its checkpoint",
            ),
            (StepDone(step=ProgressStep.HISTORY_SAVE), "Step history_save done"),
            (
                StrategyChosen(
                    attempt=1,
                    strategy=DiscoveryArtistStrategyFactory.build(artists=ArtistSuggestedFactory.batch(6)),
                ),
                "Attempt 1: 6 artists suggested",
            ),
            (
                CandidatesFound(
                    attempt=1,
                    searches=[
                        ArtistSearch(artist="Artist A", found=10, matched=8, tracks=TrackFactory.batch(3)),
                        ArtistSearch(artist="Artist B", found=0, matched=0, tracks=[]),
                    ],
                ),
                "Attempt 1: 3 unknown tracks found for 2 artists",
            ),
            (
                PicksMade(
                    attempt=1,
                    picks=[TrackPicked(track=track, score=0.9) for track in TrackFactory.batch(4)],
                    tracks=TrackFactory.batch(3),
                    target=10,
                ),
                "Attempt 1: 4 tracks picked, 3/10 kept",
            ),
        ],
    )
    async def test__publish__one_info_line(
        self,
        adapter: LogProgressAdapter,
        caplog: pytest.LogCaptureFixture,
        event: ProgressEvent,
        message: str,
    ) -> None:
        with caplog.at_level(logging.INFO):
            await adapter.publish(event)

        assert [(record.levelno, record.getMessage()) for record in caplog.records] == [(logging.INFO, message)]

    async def test__publish__playlist_created(
        self,
        adapter: LogProgressAdapter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        playlist = PlaylistFactory.build(tracks=TrackFactory.batch(2))

        with caplog.at_level(logging.INFO):
            await adapter.publish(PlaylistCreated(playlist=playlist))

        assert caplog.messages == [f"Playlist {playlist.id} created with 2 tracks"]

    @pytest.fixture
    def mock_monotonic(self) -> Iterator[mock.Mock]:
        # The adapter's clock only: the event loop keeps the real one
        with mock.patch("museflow.infrastructure.adapters.progress.log.time") as mock_time:
            yield mock_time.monotonic

    async def test__publish__step_advanced__info_now_and_then(
        self,
        adapter: LogProgressAdapter,
        caplog: pytest.LogCaptureFixture,
        mock_monotonic: mock.Mock,
    ) -> None:
        step = ProgressStep.HISTORY_SAVE

        with caplog.at_level(logging.DEBUG):
            mock_monotonic.return_value = 100.0
            await adapter.publish(StepStarted(step=step, total=60))
            await adapter.publish(StepAdvanced(step=step, done=20, total=60))
            mock_monotonic.return_value = 131.0
            await adapter.publish(StepAdvanced(step=step, done=40, total=60))
            await adapter.publish(StepAdvanced(step=step, done=60, total=60))

        assert [(record.levelno, record.getMessage()) for record in caplog.records[1:]] == [
            (logging.DEBUG, "Step history_save: 20/60"),
            (logging.INFO, "Step history_save: 40/60"),
            (logging.DEBUG, "Step history_save: 60/60"),
        ]
