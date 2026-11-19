from abc import ABC
from abc import abstractmethod

from museflow.application.inputs.history import StreamingHistoryEntryInput
from museflow.application.inputs.history import StreamingHistoryFileStats


class StreamingHistoryPort(ABC):
    @property
    @abstractmethod
    def file_pattern(self) -> str:
        """Shell-style pattern (`fnmatch`) matching the names of the provider's streaming history files in an export."""

    @abstractmethod
    async def parse_file(
        self,
        content: bytes,
        min_ms_played: int,
    ) -> tuple[list[StreamingHistoryEntryInput], StreamingHistoryFileStats]:
        """Parses the content of one streaming history file.

        Raises:
            StreamingHistoryInvalidFormatError: If the content is not a valid streaming history file.
        """
