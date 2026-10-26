from abc import ABC
from abc import abstractmethod
from pathlib import Path

from museflow.application.inputs.history import StreamingHistoryEntry
from museflow.application.inputs.history import StreamingHistoryFileStats


class StreamingHistoryPort(ABC):
    @property
    @abstractmethod
    def file_glob(self) -> str:
        """Glob matching the provider's streaming history files in an export directory."""

    @abstractmethod
    async def parse_file(
        self,
        path: Path,
        min_ms_played: int,
    ) -> tuple[list[StreamingHistoryEntry], StreamingHistoryFileStats]: ...
