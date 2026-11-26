from abc import ABC
from abc import abstractmethod
from collections.abc import Iterator

from museflow.application.outputs.archive import ArchiveFile


class ArchivePort(ABC):
    """Extracts the files of an archive a user gives: untrusted input, capped while it is extracted."""

    @abstractmethod
    def extract_files(self, content: bytes, pattern: str) -> Iterator[ArchiveFile]:
        """Yields the files whose name matches the shell-style pattern (`fnmatch`), wherever they sit in the archive,
        one at a time: only one file is held in memory.

        Raises:
            ArchiveInvalidError: If the archive can't be read.
            ArchiveTooLargeError: If it holds too many entries, or a file kept decompresses beyond a cap.
        """
