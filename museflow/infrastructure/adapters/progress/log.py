import logging
import time
from typing import Final
from typing import assert_never

from museflow.application.outputs.progress import CandidatesFound
from museflow.application.outputs.progress import PicksMade
from museflow.application.outputs.progress import PlaylistCreated
from museflow.application.outputs.progress import ProgressEvent
from museflow.application.outputs.progress import StepAdvanced
from museflow.application.outputs.progress import StepDone
from museflow.application.outputs.progress import StepResumed
from museflow.application.outputs.progress import StepStarted
from museflow.application.outputs.progress import StrategyChosen
from museflow.application.ports.progress import ProgressPort

logger = logging.getLogger(__name__)


class LogProgressAdapter(ProgressPort):
    """Writes the progress of a flow run by a worker to the logs, for an operator following it.

    One INFO line per step that starts, resumes or ends, and per outcome. A step that advances unit by unit (a chunk of
    20 tracks) logs at DEBUG, with an INFO line now and then: a job running for minutes leaves a trace, so that it can
    be told from a stuck one, without a line per chunk. Counts only, never the user's tracks or artists.
    """

    # The least time between two INFO lines of an advancing step
    _ADVANCED_INFO_INTERVAL_SECONDS: Final[float] = 30.0

    def __init__(self) -> None:
        self._advanced_info_at = time.monotonic()

    async def publish(self, event: ProgressEvent) -> None:
        match event:
            case StepStarted():
                self._advanced_info_at = time.monotonic()
                total = f" ({event.total} units)" if event.total is not None else ""
                attempt = f", attempt {event.attempt}" if event.attempt is not None else ""
                logger.info(
                    f"Step {event.step} started{total}{attempt}",
                    extra={"step": event.step, "total": event.total, "attempt": event.attempt},
                )
            case StepAdvanced():
                self._advance(event)
            case StepResumed():
                logger.info(
                    f"Step {event.step} resumed at {event.done}/{event.total} from its checkpoint",
                    extra={"step": event.step, "done": event.done, "total": event.total},
                )
            case StepDone():
                logger.info(f"Step {event.step} done", extra={"step": event.step})
            case StrategyChosen():
                logger.info(
                    f"Attempt {event.attempt}: {len(event.strategy.artists)} artists suggested",
                    extra={"attempt": event.attempt, "artists": len(event.strategy.artists)},
                )
            case CandidatesFound():
                tracks = sum(len(search.tracks) for search in event.searches)
                logger.info(
                    f"Attempt {event.attempt}: {tracks} unknown tracks found for {len(event.searches)} artists",
                    extra={"attempt": event.attempt, "tracks": tracks, "artists": len(event.searches)},
                )
            case PicksMade():
                logger.info(
                    f"Attempt {event.attempt}: {len(event.picks)} tracks picked, {len(event.tracks)}/{event.target} kept",
                    extra={"attempt": event.attempt, "picks": len(event.picks), "kept": len(event.tracks)},
                )
            case PlaylistCreated():
                logger.info(
                    f"Playlist {event.playlist.id} created with {len(event.playlist.tracks)} tracks",
                    extra={"playlist_id": event.playlist.id, "tracks": len(event.playlist.tracks)},
                )
            case _:
                # An event added to the union without a case here: mypy fails
                assert_never(event)

    def _advance(self, event: StepAdvanced) -> None:
        level = logging.DEBUG
        if time.monotonic() - self._advanced_info_at >= self._ADVANCED_INFO_INTERVAL_SECONDS:
            self._advanced_info_at = time.monotonic()
            level = logging.INFO

        logger.log(
            level,
            f"Step {event.step}: {event.done}/{event.total}",
            extra={"step": event.step, "done": event.done, "total": event.total},
        )
