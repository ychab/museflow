import enum

import typer
from rich.console import Console

from museflow.domain.types import TrackSource

app = typer.Typer()
console = Console()


class SourceFilter(enum.StrEnum):
    ALL = "all"
    HISTORY = "history"
    DISCOVERY = "discovery"

    def to_track_source(self) -> TrackSource | None:
        if self == SourceFilter.HISTORY:
            return TrackSource.HISTORY
        if self == SourceFilter.DISCOVERY:
            return TrackSource.DISCOVERY
        return None


import museflow.infrastructure.entrypoints.cli.commands.stats.artists  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.stats.candidates  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.stats.tracks  # noqa: F401,E402
