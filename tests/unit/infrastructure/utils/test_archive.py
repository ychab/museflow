import io
import zipfile
from typing import Final

import pytest

from museflow.domain.exceptions import ArchiveInvalidError
from museflow.domain.exceptions import ArchiveTooLargeError
from museflow.infrastructure.utils.archive import ArchiveLimits
from museflow.infrastructure.utils.archive import extract_files

PATTERN: Final[str] = "Streaming_History_Audio_*.json"
KB: Final[int] = 1024


class TestExtractFiles:
    @pytest.fixture
    def limits(self) -> ArchiveLimits:
        return ArchiveLimits(max_file_size=10 * KB, max_total_size=15 * KB, max_entries=3)

    @pytest.mark.parametrize(
        "zip_archive",
        [
            {
                "folder/": b"",
                "folder/Streaming_History_Audio_1.json": b"1",
                "folder/Userdata.json": b"{}",
            }
        ],
        indirect=True,
    )
    def test__other_entries__skipped(self, zip_archive: bytes, limits: ArchiveLimits) -> None:
        files = list(extract_files(zip_archive, pattern=PATTERN, limits=limits))

        assert [(file.rank, file.name, file.content) for file in files] == [
            (1, "Streaming_History_Audio_1.json", b"1")
        ]

    @pytest.mark.parametrize(
        "zip_archive",
        [{f"Streaming_History_Audio_{i}.json": b"1" for i in range(4)}],
        indirect=True,
    )
    def test__too_many_entries(self, zip_archive: bytes, limits: ArchiveLimits) -> None:
        with pytest.raises(ArchiveTooLargeError, match="up to 4 entries, over 3"):
            list(extract_files(zip_archive, pattern=PATTERN, limits=limits))

    @pytest.mark.parametrize(
        "zip_archive",
        # Each under the cap of a file, together over the cap of the whole
        [{"Streaming_History_Audio_1.json": b"0" * 8 * KB, "Streaming_History_Audio_2.json": b"0" * 8 * KB}],
        indirect=True,
    )
    def test__too_large__extracted_size(self, zip_archive: bytes, limits: ArchiveLimits) -> None:
        files = extract_files(zip_archive, pattern=PATTERN, limits=limits)

        assert next(files).rank == 0
        with pytest.raises(ArchiveTooLargeError, match="Entry 1"):
            next(files)

    @pytest.mark.parametrize(
        "zip_archive",
        [{"Streaming_History_Audio_1.json": b"a few plays, " * 100}],
        indirect=True,
    )
    def test__damaged_entry(self, zip_archive: bytes, limits: ArchiveLimits) -> None:
        # A byte of the compressed data changed: its checksum, or the stream itself, no longer holds
        damaged = bytearray(zip_archive)
        damaged[zip_archive.index(b"_1.json") + len(b"_1.json") + 4] ^= 0xFF

        with pytest.raises(ArchiveInvalidError, match="Entry 0 of the archive can't be read"):
            list(extract_files(bytes(damaged), pattern=PATTERN, limits=limits))

    def test__damaged_entry__bzip2(self, limits: ArchiveLimits) -> None:
        # Another compression, other errors: bzip2 raises an OSError on corrupt data
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("Streaming_History_Audio_1.json", b"a few plays, " * 100)
        damaged = bytearray(buffer.getvalue())
        damaged[damaged.index(b"_1.json") + len(b"_1.json") + 10] ^= 0xFF

        with pytest.raises(ArchiveInvalidError, match="Entry 0 of the archive can't be read: OSError"):
            list(extract_files(bytes(damaged), pattern=PATTERN, limits=limits))
