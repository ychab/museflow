from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ArchiveFile:
    """A file extracted from an archive."""

    rank: int  # the position of its entry in the archive: tells two files of the same name apart
    name: str  # the file name alone: the path the archive gives it is never used
    content: bytes
