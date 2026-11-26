from collections.abc import Iterator

from museflow.application.outputs.archive import ArchiveFile
from museflow.application.ports.archive import ArchivePort
from museflow.infrastructure.utils.archive import ArchiveLimits
from museflow.infrastructure.utils.archive import extract_files


class ZipArchiveAdapter(ArchivePort):
    """Extracts a zip archive within the caps it is given (see `infrastructure/utils/archive.py`)."""

    def __init__(self, limits: ArchiveLimits) -> None:
        self._limits = limits

    def extract_files(self, content: bytes, pattern: str) -> Iterator[ArchiveFile]:
        return extract_files(content, pattern=pattern, limits=self._limits)
