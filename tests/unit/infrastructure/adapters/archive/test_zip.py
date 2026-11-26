import io
import zipfile
from typing import Final

import pytest

from museflow.domain.exceptions import ArchiveInvalidError
from museflow.domain.exceptions import ArchiveTooLargeError
from museflow.infrastructure.adapters.archive.zip import ArchiveLimits
from museflow.infrastructure.adapters.archive.zip import ZipArchiveAdapter

PATTERN: Final[str] = "Streaming_History_Audio_*.json"
KB: Final[int] = 1024


class TestZipArchiveAdapter:
    @pytest.fixture
    def archive_reader(self) -> ZipArchiveAdapter:
        return ZipArchiveAdapter(limits=ArchiveLimits(max_file_size=10 * KB, max_total_size=15 * KB, max_entries=3))

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
    def test__other_entries__skipped(self, zip_archive: bytes, archive_reader: ZipArchiveAdapter) -> None:
        files = list(archive_reader.extract(zip_archive, pattern=PATTERN))

        assert [(file.rank, file.name, file.content) for file in files] == [
            (1, "Streaming_History_Audio_1.json", b"1")
        ]

    @pytest.mark.parametrize(
        "zip_archive",
        [{f"Streaming_History_Audio_{i}.json": b"1" for i in range(4)}],
        indirect=True,
    )
    def test__too_many_entries(self, zip_archive: bytes, archive_reader: ZipArchiveAdapter) -> None:
        with pytest.raises(ArchiveTooLargeError, match="up to 4 entries, over 3"):
            list(archive_reader.extract(zip_archive, pattern=PATTERN))

    @pytest.mark.parametrize(
        "zip_archive",
        # Each under the cap of a file, together over the cap of the whole
        [{"Streaming_History_Audio_1.json": b"0" * 8 * KB, "Streaming_History_Audio_2.json": b"0" * 8 * KB}],
        indirect=True,
    )
    def test__too_large__extracted_size(self, zip_archive: bytes, archive_reader: ZipArchiveAdapter) -> None:
        files = archive_reader.extract(zip_archive, pattern=PATTERN)

        assert next(files).rank == 0
        with pytest.raises(ArchiveTooLargeError, match="Entry 1"):
            next(files)

    @pytest.mark.parametrize(
        "zip_archive",
        [{"Streaming_History_Audio_1.json": b"a few plays, " * 100}],
        indirect=True,
    )
    def test__damaged_entry(self, zip_archive: bytes, archive_reader: ZipArchiveAdapter) -> None:
        # A byte of the compressed data changed: its checksum, or the stream itself, no longer holds
        damaged = bytearray(zip_archive)
        damaged[zip_archive.index(b"_1.json") + len(b"_1.json") + 4] ^= 0xFF

        with pytest.raises(ArchiveInvalidError, match="Entry 0 of the archive can't be read"):
            list(archive_reader.extract(bytes(damaged), pattern=PATTERN))

    def test__damaged_entry__bzip2(self, archive_reader: ZipArchiveAdapter) -> None:
        # Another compression, other errors: bzip2 raises an OSError on corrupt data
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("Streaming_History_Audio_1.json", b"a few plays, " * 100)
        damaged = bytearray(buffer.getvalue())
        damaged[damaged.index(b"_1.json") + len(b"_1.json") + 10] ^= 0xFF

        with pytest.raises(ArchiveInvalidError, match="Entry 0 of the archive can't be read: OSError"):
            list(archive_reader.extract(bytes(damaged), pattern=PATTERN))
