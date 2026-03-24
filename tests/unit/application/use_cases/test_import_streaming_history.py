import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryUseCase
from museflow.domain.entities.user import User
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.exceptions import StreamingHistoryInvalidFormat
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource

from tests.unit.factories.entities.music import TrackFactory


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def json_file(self, request: pytest.FixtureRequest, tmp_path: Path) -> Path:
        params = getattr(request, "param", {})

        filename: Path = params.get("filename", Path("history.json"))
        entries: list[dict[str, Any]] = params.get("entries", [])
        content: str | None = params.get("content", None)

        filepath = tmp_path / filename
        filepath.write_text(content or json.dumps(entries))

        return filepath

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
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 25000, "spotify_track_uri": "spotify:track:track2"},  # ms_played too low
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
                    {"ms_played": 60000, "spotify_track_uri": None},  # Missing URI
                    {"ms_played": 60000, "spotify_track_uri": "spotify:episode:ep1"},  # Not a track
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
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
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
                    {"ms_played": 100, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 200, "spotify_track_uri": "spotify:track:track2"},
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
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
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
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
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
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track1"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track2"},
                    {"ms_played": 60000, "spotify_track_uri": "spotify:track:track3"},
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
