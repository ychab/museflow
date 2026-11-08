import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.inputs.history import StreamingHistoryFileStats
from museflow.application.use_cases.history_import import ImportStreamingHistoryUseCase
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFoundError
from museflow.domain.value_objects.track import TrackPlay

from tests.unit.factories.inputs.history import StreamingHistoryEntryFactory


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def history_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "Streaming_History_Audio_0.json").write_text("[]")
        return tmp_path

    @pytest.fixture(autouse=True)
    def track_ids(self, mock_track_repository: mock.AsyncMock) -> dict[str, uuid.UUID]:
        """The upsert returns an id per fingerprint, as the repository does; the fixture keeps them by fingerprint."""
        track_ids: dict[str, uuid.UUID] = {}

        def upsert(tracks: list[Track], batch_size: int) -> tuple[dict[str, uuid.UUID], int]:
            ids = {track.fingerprint: uuid.uuid4() for track in tracks}
            track_ids.update(ids)
            return ids, len(tracks)

        mock_track_repository.bulk_upsert.side_effect = upsert
        return track_ids

    @pytest.fixture
    def use_case(
        self,
        mock_uow: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(
            uow=mock_uow,
            streaming_history=mock_streaming_history,
        )

    async def test__tracks_built_from_file_metadata(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        entries = [
            StreamingHistoryEntryFactory.build(
                provider_id="track1", name="Song Name", artist="Artist Name", album_name="Album Name"
            ),
            StreamingHistoryEntryFactory.build(provider_id="track2"),
        ]
        mock_streaming_history.parse_file.return_value = (entries, StreamingHistoryFileStats())

        await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=history_dir),
        )

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        assert len(upserted) == 2
        upserted_by_id = {t.get_provider_id(MusicProvider.SPOTIFY): t for t in upserted}

        track1 = upserted_by_id["track1"]
        assert track1.name == "Song Name"
        assert track1.artists == ["Artist Name"]
        assert track1.album_name == "Album Name"
        assert track1.user_id == user.id
        assert track1.provider_links[0].provider == MusicProvider.SPOTIFY

    async def test__purge__deletes_the_unlinked_tracks(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        orphan_ids = [uuid.uuid4() for _ in range(5)]
        mock_track_repository.unlink_provider.return_value = orphan_ids
        mock_track_repository.delete.return_value = 5

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=history_dir, purge=True),
        )

        mock_track_repository.unlink_provider.assert_awaited_once_with(user_id=user.id, provider=MusicProvider.SPOTIFY)
        mock_track_repository.delete.assert_awaited_once_with(user_id=user.id, track_ids=orphan_ids)
        assert report.tracks_purged == 5

    async def test__no_tracks_parsed__nothing_saved(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=history_dir),
        )

        assert report.unique_track_ids == 0
        mock_track_repository.bulk_upsert.assert_not_called()

    async def test__directory__not_found(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(StreamingHistoryDirectoryNotFoundError):
            await use_case.import_history(
                user=user,
                config=ImportStreamingHistoryConfigInput(directory=tmp_path / "nonexistent"),
            )

    async def test__directory__no_json_files(
        self,
        user: User,
        tmp_path: Path,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        (tmp_path / "not_json.txt").write_text("")
        with pytest.raises(StreamingHistoryDirectoryNotFoundError):
            await use_case.import_history(
                user=user,
                config=ImportStreamingHistoryConfigInput(directory=tmp_path),
            )

    async def test__directory__ignores_non_audio_json_files(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        (history_dir / "Streaming_History_Video_2020_2024.json").write_text("[]")
        (history_dir / "Userdata.json").write_text("{}")
        mock_streaming_history.parse_file.return_value = ([], StreamingHistoryFileStats())

        await use_case.import_history(user=user, config=ImportStreamingHistoryConfigInput(directory=history_dir))

        mock_streaming_history.parse_file.assert_awaited_once_with(
            path=history_dir / "Streaming_History_Audio_0.json", min_ms_played=90_000
        )

    async def test__merge_across_files__every_play_saved(
        self,
        user: User,
        tmp_path: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_track_play_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
        track_ids: dict[str, uuid.UUID],
    ) -> None:
        (tmp_path / "Streaming_History_Audio_1.json").write_text("[]")
        (tmp_path / "Streaming_History_Audio_2.json").write_text("[]")

        mock_streaming_history.parse_file.side_effect = [
            (
                [
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_1",
                        name="Song 1",
                        artist="Artist",
                        played_at=datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
                    ),
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_2",
                        name="Song 2",
                        artist="Artist",
                        played_at=datetime(2023, 1, 5, 10, 0, 0, tzinfo=UTC),
                    ),
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_4",
                        name="Song 4",
                        artist="Artist",
                        played_at=datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
                    ),
                ],
                StreamingHistoryFileStats(),
            ),
            (
                [
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_1",
                        name="Song 1",
                        artist="Artist",
                        played_at=datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC),
                    ),
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_2",
                        name="Song 2",
                        artist="Artist",
                        played_at=datetime(2023, 1, 4, 10, 0, 0, tzinfo=UTC),
                    ),
                    StreamingHistoryEntryFactory.build(
                        provider_id="track_3",
                        name="Song 3",
                        artist="Artist",
                        played_at=datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC),
                    ),
                ],
                StreamingHistoryFileStats(),
            ),
        ]

        await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        plays: list[TrackPlay] = mock_track_play_repository.bulk_create.call_args.args[0]
        plays_by_provider_id = {
            track.get_provider_id(MusicProvider.SPOTIFY): sorted(
                play.played_at.day for play in plays if play.track_id == track_ids[track.fingerprint]
            )
            for track in upserted
        }
        # The plays of a track in both files are all saved, on the same track
        assert plays_by_provider_id == {"track_1": [1, 3], "track_2": [4, 5], "track_3": [2], "track_4": [1]}
