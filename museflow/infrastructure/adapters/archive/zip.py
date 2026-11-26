import asyncio
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Final

from museflow.application.outputs.archive import ArchiveFile
from museflow.application.ports.archive import ArchivePort
from museflow.domain.exceptions import ArchiveInvalidError
from museflow.domain.exceptions import ArchiveTooLargeError


@dataclass(frozen=True, kw_only=True)
class ArchiveLimits:
    max_file_size: int  # bytes decompressed for one file
    max_total_size: int  # bytes decompressed for all the files kept
    max_entries: int  # entries of the archive, kept or not


class ZipArchiveAdapter(ArchivePort):
    """Zip archives a user gives: untrusted input, checked before it is stored, capped while it is extracted.

    The caps count the bytes really decompressed, never the sizes the archive declares, which a zip bomb fakes.
    """

    # The first bytes of a zip archive (a local file header): what the file is, whatever its name and media type claim
    _SIGNATURE: Final[bytes] = b"PK\x03\x04"
    # The start of each record of the central directory, one per entry: counted before the archive is opened, which
    # reads them all (a 94 MB archive of 2 million empty entries takes seconds and a GB of memory)
    _CENTRAL_DIRECTORY_SIGNATURE: Final[bytes] = b"PK\x01\x02"
    # Bytes decompressed at a time: the caps are checked between two reads, so a bomb never gets further than one more
    _READ_CHUNK_SIZE: Final[int] = 1024 * 1024

    def __init__(self, limits: ArchiveLimits) -> None:
        self._limits = limits

    async def check(self, content: bytes) -> None:
        # Reads the central directory: off the event loop, which other requests share
        await asyncio.to_thread(self._check, content)

    def extract(self, content: bytes, pattern: str) -> Iterator[ArchiveFile]:
        with self._open(content) as archive:
            extracted_size = 0
            for rank, entry in enumerate(archive.infolist()):
                # The file name alone, whatever the path (`../../`, absolute, Windows separators): no path traversal
                name = PurePosixPath(entry.filename.replace("\\", "/")).name
                if entry.is_dir() or not fnmatchcase(name, pattern):
                    continue

                max_size = min(self._limits.max_file_size, self._limits.max_total_size - extracted_size)
                file_content = self._read(archive, entry, rank=rank, max_size=max_size)
                extracted_size += len(file_content)

                yield ArchiveFile(rank=rank, name=name, content=file_content)

    def _check(self, content: bytes) -> None:
        if not content.startswith(self._SIGNATURE):
            raise ArchiveInvalidError("Not a zip archive")

        with self._open(content):
            pass

    def _open(self, content: bytes) -> zipfile.ZipFile:
        # A signature inside compressed data counts too: an archive may be refused for a few entries short of the cap,
        # never let through over it
        entries_count = content.count(self._CENTRAL_DIRECTORY_SIGNATURE)
        if entries_count > self._limits.max_entries:
            raise ArchiveTooLargeError(
                f"The archive holds up to {entries_count} entries, over {self._limits.max_entries}"
            )

        # Any error: zipfile documents no set of errors on a damaged archive (see `_read`)
        try:
            return zipfile.ZipFile(io.BytesIO(content))
        except Exception as e:
            raise ArchiveInvalidError(f"Unreadable zip archive: {type(e).__name__}") from e

    def _read(self, archive: zipfile.ZipFile, entry: zipfile.ZipInfo, rank: int, max_size: int) -> bytes:
        content = bytearray()

        # Any error but our cap: zipfile documents no set of errors on a damaged entry. Fuzzing it (bytes changed at
        # random) raised BadZipFile, OSError and LZMAError (bzip2, lzma), zlib.error, ValueError, UnicodeDecodeError,
        # EOFError, NotImplementedError (an unknown compression) and RuntimeError (an encrypted entry). The block only
        # reads.
        try:
            with archive.open(entry) as file:
                while chunk := file.read(self._READ_CHUNK_SIZE):
                    content += chunk
                    if len(content) > max_size:
                        raise ArchiveTooLargeError(f"Entry {rank} of the archive decompresses beyond the caps")
        except ArchiveTooLargeError:
            raise
        except Exception as e:
            raise ArchiveInvalidError(f"Entry {rank} of the archive can't be read: {type(e).__name__}") from e

        return bytes(content)
