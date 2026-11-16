import io
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from rich.console import Console

from museflow.domain.enums import ProgressStep
from museflow.domain.enums import ReasoningEffort
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.progress import PicksMade
from museflow.domain.value_objects.progress import PlaylistCreated
from museflow.domain.value_objects.progress import StepStarted
from museflow.domain.value_objects.progress import StrategyChosen
from museflow.domain.value_objects.taste import TrackPicked
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.discovery import ArtistSuggestedFactory
from tests.unit.factories.value_objects.discovery import DiscoveryArtistStrategyFactory


class TestRichProgressAdapter:
    @pytest.fixture
    def output(self) -> io.StringIO:
        return io.StringIO()

    @pytest.fixture
    def meter(self) -> LLMUsageMeter:
        return LLMUsageMeter()

    @pytest.fixture
    def adapter(self, output: io.StringIO, meter: LLMUsageMeter) -> RichProgressAdapter:
        return RichProgressAdapter(console=Console(file=output, width=120), meter=meter, animated=False)

    async def test__steps__one_line_each__attempt_header_once(
        self,
        adapter: RichProgressAdapter,
        output: io.StringIO,
    ) -> None:
        strategy = DiscoveryArtistStrategyFactory.build(
            strategy_label="Late-night soul", artists=ArtistSuggestedFactory.batch(6)
        )
        playlist = PlaylistFactory.build(tracks=TrackFactory.batch(2))

        with adapter:
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=1, max_attempts=3))
            await adapter.publish(StrategyChosen(attempt=1, strategy=strategy))
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1))
            await adapter.publish(CandidatesFound(attempt=1, artists=6, artists_kept=5, tracks=104))
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
            picks = [TrackPicked(track=track, score=0.9) for track in TrackFactory.batch(8)]
            await adapter.publish(PicksMade(attempt=1, picks=picks, kept=7, target=10))
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=2))
            await adapter.publish(StepStarted(step=ProgressStep.PLAYLIST_CREATE))
            await adapter.publish(PlaylistCreated(playlist=playlist))

        lines = [line.strip() for line in output.getvalue().splitlines()]
        assert lines[0] == "Attempt 1/3"
        assert lines[1].startswith("✓ Artists suggested   6 · Late-night soul")
        assert lines[2].startswith("✓ Catalogue searched  104 unknown track(s) · 5/6 artists")
        assert lines[3].startswith("✓ Tracks picked       8 → 7/10 kept")
        # The next attempt gets its header, without a total when the event carries none
        assert lines[4] == "Attempt 2"
        assert lines[5].startswith("✓ Playlist created    2 track(s)")
        assert len(lines) == 6

    async def test__cost__shown_when_the_step_spent(
        self,
        adapter: RichProgressAdapter,
        output: io.StringIO,
        meter: LLMUsageMeter,
    ) -> None:
        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1))
        await adapter.publish(CandidatesFound(attempt=1, artists=1, artists_kept=1, tracks=1))
        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
        meter.record(
            "advisor_picks", "openai/gpt-5-mini", ReasoningEffort.LOW, ChatUsage(cost=Decimal("0.0211")), timedelta(0)
        )
        await adapter.publish(PicksMade(attempt=1, picks=[], kept=0, target=1))

        search_line, picks_line = output.getvalue().splitlines()[1:]
        assert search_line.rstrip().endswith("s")
        assert "$" not in search_line
        assert picks_line.rstrip().endswith("s · $0.0211")

    async def test__no_meter__no_cost(self, output: io.StringIO) -> None:
        adapter = RichProgressAdapter(console=Console(file=output, width=120), animated=False)

        await adapter.publish(StepStarted(step=ProgressStep.PLAYLIST_CREATE))
        await adapter.publish(PlaylistCreated(playlist=PlaylistFactory.build()))

        assert "$" not in output.getvalue()

    async def test__animated__status_follows_the_step(self) -> None:
        console = mock.Mock(spec=Console)
        status = console.status.return_value

        with RichProgressAdapter(console=console) as adapter:
            status.start.assert_called_once_with()
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
            status.update.assert_called_once_with("Picking tracks…")

        status.stop.assert_called_once_with()

    async def test__animated__status_stopped_on_error(self) -> None:
        console = mock.Mock(spec=Console)

        with pytest.raises(RuntimeError), RichProgressAdapter(console=console):
            raise RuntimeError("Boom")

        console.status.return_value.stop.assert_called_once_with()

    def test__not_animated__no_status(self) -> None:
        console = mock.Mock(spec=Console)

        with RichProgressAdapter(console=console, animated=False):
            pass

        console.status.assert_not_called()
