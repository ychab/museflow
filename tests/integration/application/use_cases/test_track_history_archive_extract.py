from typing import Final

import pytest

from museflow.application.use_cases.track_history_archive_extract import extract_history_archive
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ArchiveTooLargeError
from museflow.domain.exceptions import StreamingHistoryFilesNotFoundError
from museflow.infrastructure.adapters.archive.zip import ZipArchiveAdapter
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter
from museflow.infrastructure.adapters.storage.local import LocalFileStorage
from museflow.infrastructure.utils.archive import ArchiveLimits


class TestExtractHistoryArchive:
    PREFIX: Final[str] = "history/batch/files"

    @pytest.fixture
    def archive_extractor(self) -> ZipArchiveAdapter:
        return ZipArchiveAdapter(limits=ArchiveLimits(max_file_size=1024, max_total_size=2048, max_entries=3))

    @pytest.mark.parametrize(
        "zip_archive",
        [
            {
                "Spotify Extended Streaming History/Streaming_History_Audio_2017.json": b"[1]",
                "Spotify Extended Streaming History/Streaming_History_Video_2017.json": b"[2]",
                "Streaming_History_Audio_2018.json": b"[3]",
            }
        ],
        indirect=True,
    )
    async def test__nominal(
        self,
        user: User,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        archive_extractor: ZipArchiveAdapter,
    ) -> None:
        files_count = await extract_history_archive(
            user=user,
            archive=zip_archive,
            prefix=self.PREFIX,
            file_storage=file_storage,
            archive_extractor=archive_extractor,
            streaming_history=SpotifyStreamingHistoryAdapter(),
        )

        # The streaming history files alone, each under the folder of its rank in the archive
        assert files_count == 2
        assert await file_storage.list_keys(user_id=user.id, prefix=self.PREFIX) == [
            f"{self.PREFIX}/0/Streaming_History_Audio_2017.json",
            f"{self.PREFIX}/2/Streaming_History_Audio_2018.json",
        ]
        key = f"{self.PREFIX}/2/Streaming_History_Audio_2018.json"
        assert await file_storage.get(user_id=user.id, key=key) == b"[3]"

    @pytest.mark.parametrize("zip_archive", [{"Spotify Account Data/Userdata.json": b"{}"}], indirect=True)
    async def test__no_history_file(
        self,
        user: User,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        archive_extractor: ZipArchiveAdapter,
    ) -> None:
        with pytest.raises(StreamingHistoryFilesNotFoundError, match="files found in the archive"):
            await extract_history_archive(
                user=user,
                archive=zip_archive,
                prefix=self.PREFIX,
                file_storage=file_storage,
                archive_extractor=archive_extractor,
                streaming_history=SpotifyStreamingHistoryAdapter(),
            )

    @pytest.mark.parametrize(
        "zip_archive",
        [{f"Streaming_History_Audio_{year}.json": b"0" * 1000 for year in (2017, 2018, 2019)}],
        indirect=True,
    )
    async def test__too_large__files_written_kept(
        self,
        user: User,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        archive_extractor: ZipArchiveAdapter,
    ) -> None:
        with pytest.raises(ArchiveTooLargeError):
            await extract_history_archive(
                user=user,
                archive=zip_archive,
                prefix=self.PREFIX,
                file_storage=file_storage,
                archive_extractor=archive_extractor,
                streaming_history=SpotifyStreamingHistoryAdapter(),
            )

        # Over the cap of the whole at the third file: the two written before stay, for the caller to delete
        assert len(await file_storage.list_keys(user_id=user.id, prefix=self.PREFIX)) == 2
