from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from museflow.application.inputs.history import StreamingHistoryFileStats
from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.use_cases.history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.history_import import ImportStreamingHistoryUseCase
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.value_objects.track import TrackKnowIdentifiers

from tests.unit.factories.inputs.history import StreamingHistoryEntryFactory


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def history_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "history.json").write_text("[]")
        return tmp_path

    @pytest.fixture
    def use_case(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(
            track_repository=mock_track_repository,
            streaming_history=mock_streaming_history,
        )

    async def test__nominal(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        entries = StreamingHistoryEntryFactory.batch(2)
        mock_streaming_history.parse_file.return_value = (
            entries,
            StreamingHistoryFileStats(items_read=5, items_skipped_short_play=1, items_skipped_no_track_id=2),
        )
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())
        mock_track_repository.bulk_upsert.return_value = ([], 2)

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir, min_ms_played=30_000),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=5,
            items_skipped_no_timestamp=0,
            items_skipped_short_play=1,
            items_skipped_no_track_id=2,
            unique_track_ids=2,
            tracks_already_known=0,
            tracks_played_at_updated=0,
            plays_total=2,
            tracks_created=2,
            tracks_purged=0,
        )
        assert mock_track_repository.purge.call_count == 0

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
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())
        mock_track_repository.bulk_upsert.return_value = ([], 2)

        await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir),
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

    async def test__filter__already_known(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        entries = [
            StreamingHistoryEntryFactory.build(provider_id="track1", name="Song One", artist="Artist One"),
            StreamingHistoryEntryFactory.build(provider_id="track2", name="Song Two", artist="Artist Two"),
        ]
        fp1 = generate_fingerprint(name="Song One", artist_names=["Artist One"])
        fp2 = generate_fingerprint(name="Song Two", artist_names=["Artist Two"])

        mock_streaming_history.parse_file.return_value = (entries, StreamingHistoryFileStats())
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            fingerprints=frozenset([fp1, fp2])
        )
        mock_track_repository.bulk_upsert.return_value = ([], 0)

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir),
        )

        assert report.tracks_already_known == 2
        assert report.tracks_played_at_updated == 2
        assert report.tracks_created == 0
        get_known_call = mock_track_repository.get_known_identifiers.call_args
        assert set(get_known_call.kwargs["fingerprints"]) == {fp1, fp2}

    async def test__purge__calls_repository(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.purge.return_value = 5
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir, purge=True),
        )

        mock_track_repository.purge.assert_called_once()
        assert report.tracks_purged == 5

    async def test__no_tracks_parsed__skips_known_ids_lookup(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir),
        )

        assert report.unique_track_ids == 0
        mock_track_repository.get_known_identifiers.assert_not_called()

    async def test__directory__not_found(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(StreamingHistoryDirectoryNotFound):
            await use_case.import_history(
                user=user,
                config=StreamingHistoryImportConfigInput(directory=tmp_path / "nonexistent"),
            )

    async def test__directory__no_json_files(
        self,
        user: User,
        tmp_path: Path,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        (tmp_path / "not_json.txt").write_text("")
        with pytest.raises(StreamingHistoryDirectoryNotFound):
            await use_case.import_history(
                user=user,
                config=StreamingHistoryImportConfigInput(directory=tmp_path),
            )

    async def test__batch_size__chunks_upserts(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        mock_streaming_history.parse_file.return_value = (
            StreamingHistoryEntryFactory.batch(3),
            StreamingHistoryFileStats(),
        )
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())
        mock_track_repository.bulk_upsert.side_effect = [([], 1), ([], 1), ([], 1)]

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir, batch_size=1),
        )

        assert report.tracks_created == 3
        assert mock_track_repository.bulk_upsert.call_count == 3

    async def test__merge_across_files__keeps_latest_played_at(
        self,
        user: User,
        tmp_path: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        (tmp_path / "file1.json").write_text("[]")
        (tmp_path / "file2.json").write_text("[]")

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
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())
        mock_track_repository.bulk_upsert.return_value = ([], 4)

        await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=tmp_path),
        )

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        upserted_by_id = {t.get_provider_id(MusicProvider.SPOTIFY): t for t in upserted}

        assert upserted_by_id["track_1"].played_at_last == datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_2"].played_at_last == datetime(2023, 1, 5, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_3"].played_at_last == datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_4"].played_at_last == datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)

    async def test__same_fingerprint__different_provider_ids__deduplicates(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        """Two entries with different provider_ids but same name+artist collapse into one track."""
        entries = [
            StreamingHistoryEntryFactory.build(
                provider_id="single_version",
                name="My Song",
                artist="My Artist",
                played_at=datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
            StreamingHistoryEntryFactory.build(
                provider_id="album_version",
                name="My Song",
                artist="My Artist",
                played_at=datetime(2023, 2, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ]
        mock_streaming_history.parse_file.return_value = (entries, StreamingHistoryFileStats())
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(fingerprints=frozenset())
        mock_track_repository.bulk_upsert.return_value = ([], 1)

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir),
        )

        assert report.unique_track_ids == 1
        assert report.plays_total == 2

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        assert len(upserted) == 1
        assert upserted[0].played_count == 2
        assert upserted[0].played_at_first == datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
        assert upserted[0].played_at_last == datetime(2023, 2, 1, 10, 0, 0, tzinfo=UTC)

    async def test__known_tracks__played_at_refreshed(
        self,
        user: User,
        history_dir: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
        mock_streaming_history: mock.AsyncMock,
    ) -> None:
        entries = [
            StreamingHistoryEntryFactory.build(
                provider_id="track1",
                name="Song One",
                artist="Artist One",
                played_at=datetime(2024, 3, 1, 10, 0, 0, tzinfo=UTC),
            ),
            StreamingHistoryEntryFactory.build(
                provider_id="track2",
                name="Song Two",
                artist="Artist Two",
                played_at=datetime(2024, 3, 2, 12, 0, 0, tzinfo=UTC),
            ),
        ]
        fp1 = generate_fingerprint(name="Song One", artist_names=["Artist One"])
        fp2 = generate_fingerprint(name="Song Two", artist_names=["Artist Two"])

        mock_streaming_history.parse_file.return_value = (entries, StreamingHistoryFileStats())
        mock_track_repository.get_known_identifiers.return_value = TrackKnowIdentifiers(
            fingerprints=frozenset([fp1, fp2])
        )
        mock_track_repository.bulk_upsert.return_value = ([], 0)

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=history_dir),
        )

        assert report.tracks_played_at_updated == 2
        assert report.tracks_created == 0

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        upserted_by_id = {t.get_provider_id(MusicProvider.SPOTIFY): t for t in upserted}
        assert upserted_by_id["track1"].played_at_last == datetime(2024, 3, 1, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track2"].played_at_last == datetime(2024, 3, 2, 12, 0, 0, tzinfo=UTC)
