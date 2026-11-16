import io
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from rich.console import Console
from rich.progress import MofNCompleteColumn
from rich.progress import Progress
from rich.progress import TaskID
from rich.text import Text

from museflow.domain.enums import ProgressStep
from museflow.domain.enums import ReasoningEffort
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.progress import PicksMade
from museflow.domain.value_objects.progress import PlaylistCreated
from museflow.domain.value_objects.progress import StepAdvanced
from museflow.domain.value_objects.progress import StepDone
from museflow.domain.value_objects.progress import StepResumed
from museflow.domain.value_objects.progress import StepStarted
from museflow.domain.value_objects.progress import StrategyChosen
from museflow.domain.value_objects.taste import ArtistSearch
from museflow.domain.value_objects.taste import TrackPicked
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.adapters.progress.rich import _WithTotalOnly

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
            searches = [ArtistSearch(artist=f"Band {i}", tracks=TrackFactory.batch(2)) for i in range(5)]
            searches.append(ArtistSearch(artist="Band 5", rejected=True))
            await adapter.publish(CandidatesFound(attempt=1, searches=searches))
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
            picks = [TrackPicked(track=track, score=0.9) for track in TrackFactory.batch(8)]
            tracks = [pick.track for pick in picks[:7]]
            await adapter.publish(PicksMade(attempt=1, picks=picks, tracks=tracks, target=10))
            await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=2))
            await adapter.publish(StepStarted(step=ProgressStep.PLAYLIST_CREATE))
            await adapter.publish(PlaylistCreated(playlist=playlist))

        lines = [line.strip() for line in output.getvalue().splitlines()]
        assert lines[0] == "Attempt 1/3"
        assert lines[1].startswith("✓ Artists suggested   6 · Late-night soul")
        assert lines[2].startswith("✓ Catalogue searched  10 unknown track(s) · 5/6 artists")
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
        await adapter.publish(CandidatesFound(attempt=1, searches=[]))
        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
        meter.record(
            "advisor_picks", "openai/gpt-5-mini", ReasoningEffort.LOW, ChatUsage(cost=Decimal("0.0211")), timedelta(0)
        )
        await adapter.publish(PicksMade(attempt=1, picks=[], tracks=[], target=1))

        search_line, picks_line = output.getvalue().splitlines()[1:]
        assert search_line.rstrip().endswith("s")
        assert "$" not in search_line
        assert picks_line.rstrip().endswith("s · $0.0211")

    async def test__verbose__details_under_the_lines(self, output: io.StringIO) -> None:
        adapter = RichProgressAdapter(console=Console(file=output, width=120), animated=False, verbose=True)
        # Brackets in a name stay as written: no Rich markup
        strategy = DiscoveryArtistStrategyFactory.build(
            strategy_label="Late-night soul",
            artists=[
                ArtistSuggestedFactory.build(name="Nova Lane", score=0.92, sound="warm Rhodes", requested=False),
                ArtistSuggestedFactory.build(name="The [Owls]", score=0.85, sound="dusty loops", requested=True),
            ],
        )
        track_kept = TrackFactory.build(name="Midnight Tram", artists=["Nova Lane"])
        track_cut = TrackFactory.build(name="Paper Moon", artists=["Nova Lane"])

        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=1))
        await adapter.publish(StrategyChosen(attempt=1, strategy=strategy))
        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1))
        searches = [
            ArtistSearch(artist="Nova Lane", found=50, matched=38, tracks=[track_kept, track_cut]),
            ArtistSearch(artist="The [Owls]", found=20, matched=20),
            ArtistSearch(artist="Bad/Name", rejected=True),
        ]
        await adapter.publish(CandidatesFound(attempt=1, searches=searches))
        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=1))
        picks = [TrackPicked(track=track_kept, score=0.95), TrackPicked(track=track_cut, score=0.71)]
        await adapter.publish(PicksMade(attempt=1, picks=picks, tracks=[track_kept], target=10))

        lines = [line.rstrip() for line in output.getvalue().splitlines()]
        assert lines[2:4] == [
            "   Nova Lane   0.92  warm Rhodes",
            "   The [Owls]  0.85  requested  dusty loops",
        ]
        assert lines[5:8] == [
            "   Nova Lane   50 found · 38 by the artist · 2 unknown",
            "   The [Owls]  20 found · 20 by the artist · 0 unknown",
            "   Bad/Name    search rejected",
        ]
        assert lines[9:] == [
            "   0.95  Nova Lane - Midnight Tram",
            "   0.71  Nova Lane - Paper Moon  cut",
        ]

    async def test__verbose__nothing_to_detail(self, output: io.StringIO) -> None:
        adapter = RichProgressAdapter(console=Console(file=output, width=120), animated=False, verbose=True)

        await adapter.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=1))
        await adapter.publish(CandidatesFound(attempt=1, searches=[]))

        assert len(output.getvalue().splitlines()) == 2

    async def test__no_meter__no_cost(self, output: io.StringIO) -> None:
        adapter = RichProgressAdapter(console=Console(file=output, width=120), animated=False)

        await adapter.publish(StepStarted(step=ProgressStep.PLAYLIST_CREATE))
        await adapter.publish(PlaylistCreated(playlist=PlaylistFactory.build()))

        assert "$" not in output.getvalue()

    async def test__batched_steps__total_in_the_line(self, adapter: RichProgressAdapter, output: io.StringIO) -> None:
        await adapter.publish(StepStarted(step=ProgressStep.ENRICH_TRACKS, total=10124))
        await adapter.publish(StepAdvanced(step=ProgressStep.ENRICH_TRACKS, done=200, total=10124))
        await adapter.publish(StepDone(step=ProgressStep.ENRICH_TRACKS))
        await adapter.publish(StepStarted(step=ProgressStep.TASTE_REFLECT))
        await adapter.publish(StepDone(step=ProgressStep.TASTE_REFLECT))

        enrich_line, reflect_line = (line.strip() for line in output.getvalue().splitlines())
        assert enrich_line.startswith("✓ Tracks enriched     10,124 track(s)")
        # A single call has no total to show
        assert reflect_line.startswith("✓ Profile reflected  ")
        assert "track(s)" not in reflect_line

    async def test__resumed__line_from_the_checkpoint(self, adapter: RichProgressAdapter, output: io.StringIO) -> None:
        await adapter.publish(StepStarted(step=ProgressStep.TASTE_PERIODS, total=4))
        await adapter.publish(StepResumed(step=ProgressStep.TASTE_PERIODS, done=2, total=4))

        assert output.getvalue().strip() == "↻ Resumed             at 2/4 period(s), from the checkpoint"

    @pytest.fixture
    def mock_progress_cls(self) -> Iterator[mock.Mock]:
        with mock.patch("museflow.infrastructure.adapters.progress.rich.Progress", autospec=True) as patched:
            yield patched

    async def test__animated__live_line_follows_the_steps(self, mock_progress_cls: mock.Mock) -> None:
        console = mock.Mock(spec=Console)
        progress = mock_progress_cls.return_value
        progress.add_task.side_effect = [TaskID(1), TaskID(2)]

        with RichProgressAdapter(console=console) as adapter:
            progress.start.assert_called_once_with()
            await adapter.publish(StepStarted(step=ProgressStep.HISTORY_SAVE, total=4))
            await adapter.publish(StepResumed(step=ProgressStep.HISTORY_SAVE, done=1, total=4))
            await adapter.publish(StepAdvanced(step=ProgressStep.HISTORY_SAVE, done=2, total=4))
            # A step started while another runs replaces it
            await adapter.publish(StepStarted(step=ProgressStep.TASTE_REFLECT))
            await adapter.publish(StepDone(step=ProgressStep.TASTE_REFLECT))

        assert progress.add_task.call_args_list == [
            mock.call("Saving tracks and plays…", total=4),
            mock.call("Reflecting on the profile…", total=None),
        ]
        assert progress.update.call_args_list == [
            mock.call(TaskID(1), completed=1, total=4),
            mock.call(TaskID(1), completed=2, total=4),
        ]
        assert progress.remove_task.call_args_list == [mock.call(TaskID(1)), mock.call(TaskID(2))]
        assert console.print.call_count == 2  # the resumed line, then the reflection's finished line
        progress.stop.assert_called_once_with()

    async def test__animated__stopped_on_error(self, mock_progress_cls: mock.Mock) -> None:
        with pytest.raises(RuntimeError), RichProgressAdapter(console=mock.Mock(spec=Console)):
            raise RuntimeError("Boom")

        mock_progress_cls.return_value.stop.assert_called_once_with()

    async def test__not_animated__no_live_line(self, mock_progress_cls: mock.Mock, output: io.StringIO) -> None:
        with RichProgressAdapter(console=Console(file=output), animated=False) as adapter:
            await adapter.publish(StepStarted(step=ProgressStep.HISTORY_SAVE, total=4))
            await adapter.publish(StepAdvanced(step=ProgressStep.HISTORY_SAVE, done=2, total=4))

        mock_progress_cls.assert_not_called()
        assert output.getvalue() == ""


class TestWithTotalOnly:
    @pytest.mark.parametrize(("total", "renders"), [(None, False), (4, True)])
    def test__render(self, total: int | None, renders: bool) -> None:
        progress = Progress()
        task_id = progress.add_task("Working", total=total)

        rendered = _WithTotalOnly(MofNCompleteColumn()).render(progress.tasks[task_id])

        assert isinstance(rendered, Text)
        assert bool(rendered.plain) is renders
