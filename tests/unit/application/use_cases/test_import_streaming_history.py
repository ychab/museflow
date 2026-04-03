import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryUseCase
from museflow.domain.entities.music import Track
from museflow.domain.entities.user import User
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.exceptions import StreamingHistoryInvalidFormat
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource

from tests.unit.factories.entities.music import TrackFactory


def build_json_file(filepath: Path, entries: list[dict[str, Any]], content: str | None = None) -> Path:
    filepath.write_text(content or json.dumps(entries))
    return filepath


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def json_file(self, request: pytest.FixtureRequest, tmp_path: Path) -> Path:
        params = getattr(request, "param", {})

        filename: Path = params.get("filename", Path("history.json"))
        entries: list[dict[str, Any]] = params.get("entries", [])
        content: str | None = params.get("content", None)

        filepath = tmp_path / filename
        return build_json_file(filepath=filepath, entries=entries, content=content)

    @pytest.fixture
    def use_case(
        self,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(
            provider_library=mock_provider_library,
            track_repository=mock_track_repository,
        )

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {
                        "ts": "2017-08-11T13:00:16Z",
                        "ms_played": 25000,
                        "spotify_track_uri": "spotify:track:track2",
                    },  # ms_played too low
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": None},  # Missing URI
                    {
                        "ts": "2017-08-11T13:00:16Z",
                        "ms_played": 60000,
                        "spotify_track_uri": "spotify:episode:ep1",
                    },  # Not a track
                ],
            },
        ],
        indirect=True,
    )
    async def test__nominal(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_1 = TrackFactory.build(user_id=user.id, provider=MusicProvider.SPOTIFY, sources=TrackSource.HISTORY)
        track_3 = TrackFactory.build(user_id=user.id, provider=MusicProvider.SPOTIFY, sources=TrackSource.HISTORY)

        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_provider_library.get_track_by_id.side_effect = [track_1, track_3]
        mock_track_repository.bulk_upsert.return_value = ([track_1.id, track_3.id], 2)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=tmp_path,
                min_ms_played=30_000,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=5,
            items_skipped_no_ts=0,
            items_skipped_duration=1,
            items_skipped_no_uri=2,
            unique_track_ids=2,
            tracks_already_known=0,
            tracks_fetched=2,
            tracks_created=2,
            tracks_purged=0,
        )
        assert mock_track_repository.purge.call_count == 0

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__filter__already_known(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track1", "track2"])

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.tracks_already_known == 2
        assert report.tracks_fetched == 0
        assert report.tracks_created == 0
        mock_provider_library.get_track_by_id.assert_not_called()
        mock_track_repository.bulk_upsert.assert_not_called()

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},  # no ts
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},  # no ts
                ],
            },
        ],
        indirect=True,
    )
    async def test__filter__no_ts(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track2"])

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.items_read == 3
        assert report.items_skipped_no_ts == 2
        assert report.unique_track_ids == 1
        mock_provider_library.get_track_by_id.assert_not_called()

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 100, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 200, "spotify_track_uri": "spotify:track:track2"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__filter__min_ms_played(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=tmp_path,
                min_ms_played=30_000,
            ),
        )

        assert report.items_read == 2
        assert report.items_skipped_duration == 2
        assert report.unique_track_ids == 0
        assert report.tracks_fetched == 0
        mock_provider_library.get_track_by_id.assert_not_called()

    async def test__directory__not_found(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(StreamingHistoryDirectoryNotFound):
            await use_case.import_history(
                user=user,
                config=ImportStreamingHistoryConfigInput(directory=tmp_path / "nonexistent"),
            )

    @pytest.mark.parametrize("json_file", [{"filename": "not_json.txt"}], indirect=True)
    async def test__directory__no_json_files(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        with pytest.raises(StreamingHistoryDirectoryNotFound):
            await use_case.import_history(
                user=user,
                config=ImportStreamingHistoryConfigInput(directory=tmp_path),
            )

    @pytest.mark.parametrize("json_file", [{"content": "{invalid json"}], indirect=True)
    async def test__directory__invalid_json_format(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        with pytest.raises(StreamingHistoryInvalidFormat):
            await use_case.import_history(
                user=user,
                config=ImportStreamingHistoryConfigInput(directory=tmp_path),
            )

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__fetch_bulk__nominal(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(
            size=3,
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            sources=TrackSource.HISTORY,
        )

        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_provider_library.get_tracks_by_ids.side_effect = [[tracks[0]], [tracks[1]], [tracks[2]]]
        mock_track_repository.bulk_upsert.side_effect = [([t.id], 1) for t in tracks]

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=tmp_path,
                batch_size=1,
                fetch_bulk=True,
            ),
        )

        assert report.tracks_fetched == 3
        assert report.tracks_created == 3
        mock_provider_library.get_track_by_id.assert_not_called()
        assert mock_provider_library.get_tracks_by_ids.call_count == 3

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__fetch_bulk__partial_results(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_1 = TrackFactory.build(user_id=user.id, provider=MusicProvider.SPOTIFY, sources=TrackSource.HISTORY)

        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_provider_library.get_tracks_by_ids.return_value = [track_1]
        mock_track_repository.bulk_upsert.return_value = ([track_1.id], 1)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path, fetch_bulk=True),
        )

        assert report.tracks_fetched == 1
        assert report.tracks_created == 1

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ts": "2017-08-11T13:00:16Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__batch_size__chunks_requests(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(
            size=3,
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            sources=TrackSource.HISTORY,
        )
        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_provider_library.get_track_by_id.side_effect = tracks
        mock_track_repository.bulk_upsert.side_effect = [([t.id], 1) for t in tracks]

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=tmp_path,
                batch_size=1,  # Forces one upsert call per track; all tracks still fetched
            ),
        )

        assert report.tracks_fetched == 3
        assert report.tracks_created == 3
        assert mock_provider_library.get_track_by_id.call_count == 3
        assert mock_track_repository.bulk_upsert.call_count == 3

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    # track1: appears 3x — newest ts wins
                    {"ts": "2023-01-02T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ts": "2023-01-03T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    # track1 again with older ts — dedup keeps newest
                    {"ts": "2023-01-01T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    # track2: appears twice; second has no ts — skipped as items_skipped_no_ts
                    {"ts": "2023-01-01T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__parse_history_file__duplicate_tracks_keeps_latest(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track1", "track2"])

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.unique_track_ids == 2
        assert report.items_read == 5
        assert report.items_skipped_no_ts == 1

    async def test__merge_across_files__keeps_latest_played_at(
        self,
        user: User,
        tmp_path: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_provider_library: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # track1: file1 older, file2 newer → file2 wins
        # track2: file1 newer, file2 older → file1 wins
        # track3: file1 no ts (skipped), file2 with ts → file2 entry only
        # track4: file1 with ts, file2 no ts (skipped) → file1 entry only
        build_json_file(
            filepath=tmp_path / "file1.json",
            entries=[
                {"ts": "2023-01-01T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_1"},
                {"ts": "2023-01-05T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_2"},
                {"ms_played": 60000, "spotify_track_uri": "spotify:track:track_3"},
                {"ts": "2023-01-01T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_4"},
            ],
        )
        build_json_file(
            filepath=tmp_path / "file2.json",
            entries=[
                {"ts": "2023-01-03T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_1"},
                {"ts": "2023-01-04T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_2"},
                {"ts": "2023-01-02T10:00:00Z", "ms_played": 60000, "spotify_track_uri": "spotify:track:track_3"},
                {"ms_played": 60000, "spotify_track_uri": "spotify:track:track_4"},
            ],
        )

        tracks: list[Track] = []
        for i in range(1, 5):
            track = TrackFactory.build(
                provider_id=f"track_{i}",
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                sources=TrackSource.HISTORY,
            )
            tracks.append(track)

        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_provider_library.get_track_by_id.side_effect = tracks
        mock_track_repository.bulk_upsert.return_value = ([t.id for t in tracks], 4)

        await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        upserted_tracks: list = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        assert upserted_tracks[0].played_at == datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC)
        assert upserted_tracks[1].played_at == datetime(2023, 1, 5, 10, 0, 0, tzinfo=UTC)
        assert upserted_tracks[2].played_at == datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC)
        assert upserted_tracks[3].played_at == datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
