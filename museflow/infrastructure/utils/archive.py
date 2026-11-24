"""Zip archives a user uploads: untrusted input, checked before it is stored, capped while it is extracted."""

import io
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Final

# The first bytes of a zip archive (a local file header): what the file is, whatever its name and media type claim
ZIP_SIGNATURE: Final[bytes] = b"PK\x03\x04"
# The start of each record of the central directory, one per entry: counted before the archive is opened, which reads
# them all (a 94 MB archive of 2 million empty entries takes seconds and a GB of memory)
_CENTRAL_DIRECTORY_SIGNATURE: Final[bytes] = b"PK\x01\x02"

# Bytes decompressed at a time: the caps are checked between two reads, so a bomb never gets further than one more
_READ_CHUNK_SIZE: Final[int] = 1024 * 1024
# What reading an entry raises on a damaged or unsupported archive: a CRC mismatch or overlapping entries
# (BadZipFile), an encrypted entry (RuntimeError), an unknown compression (NotImplementedError), corrupt data
_READ_ERRORS: Final[tuple[type[Exception], ...]] = (
    zipfile.BadZipFile,
    RuntimeError,
    NotImplementedError,
    zlib.error,
    EOFError,
)


class ArchiveInvalidError(Exception):
    """The file is not a zip archive, or one that can't be read: damaged, encrypted."""


class ArchiveTooLargeError(Exception):
    """The archive, or what it extracts to, goes beyond a cap."""


@dataclass(frozen=True, kw_only=True)
class ArchiveLimits:
    max_file_size: int  # bytes decompressed for one file
    max_extracted_size: int  # bytes decompressed for all the files kept
    max_entries: int  # entries of the archive, kept or not


@dataclass(frozen=True, kw_only=True)
class ArchiveFile:
    rank: int  # the position of its entry in the archive: tells two files of the same name apart
    name: str  # the file name alone: the path the archive gives it is never used
    content: bytes


def check_zip(content: bytes, max_entries: int) -> None:
    """Checks that the content is a readable zip archive, from its signature and its central directory, without
    decompressing anything.

    Raises:
        ArchiveInvalidError: If it is not.
        ArchiveTooLargeError: If it holds too many entries.
    """
    if not content.startswith(ZIP_SIGNATURE):
        raise ArchiveInvalidError("Not a zip archive")

    with _open(content, max_entries=max_entries):
        pass


def extract_files(content: bytes, pattern: str, limits: ArchiveLimits) -> Iterator[ArchiveFile]:
    """Yields the files of the archive whose name matches the pattern, wherever they sit in it, one at a time.

    The caps count the bytes really decompressed, never the sizes the archive declares, which a zip bomb fakes.

    Raises:
        ArchiveInvalidError: If the archive can't be read.
        ArchiveTooLargeError: If it holds too many entries, or a file kept decompresses beyond a cap.
    """
    with _open(content, max_entries=limits.max_entries) as archive:
        extracted_size = 0
        for rank, entry in enumerate(archive.infolist()):
            # The file name alone, whatever the path (`../../`, absolute, Windows separators): no path traversal
            name = PurePosixPath(entry.filename.replace("\\", "/")).name
            if entry.is_dir() or not fnmatchcase(name, pattern):
                continue

            max_size = min(limits.max_file_size, limits.max_extracted_size - extracted_size)
            file_content = _read(archive, entry, rank=rank, max_size=max_size)
            extracted_size += len(file_content)

            yield ArchiveFile(rank=rank, name=name, content=file_content)


def _open(content: bytes, max_entries: int) -> zipfile.ZipFile:
    # A signature inside compressed data counts too: an archive may be refused for a few entries short of the cap,
    # never let through over it
    entries_count = content.count(_CENTRAL_DIRECTORY_SIGNATURE)
    if entries_count > max_entries:
        raise ArchiveTooLargeError(f"The archive holds up to {entries_count} entries, over {max_entries}")

    try:
        return zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as e:
        raise ArchiveInvalidError("Unreadable zip archive") from e


def _read(archive: zipfile.ZipFile, entry: zipfile.ZipInfo, rank: int, max_size: int) -> bytes:
    content = bytearray()

    try:
        with archive.open(entry) as file:
            while chunk := file.read(_READ_CHUNK_SIZE):
                content += chunk
                if len(content) > max_size:
                    raise ArchiveTooLargeError(f"Entry {rank} of the archive decompresses beyond the caps")
    except _READ_ERRORS as e:
        raise ArchiveInvalidError(f"Entry {rank} of the archive can't be read: {type(e).__name__}") from e

    return bytes(content)
