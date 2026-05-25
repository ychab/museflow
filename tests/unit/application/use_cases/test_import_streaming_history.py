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

from tests.unit.factories.entities.music import TrackFactory


def build_json_file(filepath: Path, entries: list[dict[str, Any]], content: str | None = None) -> Path:
    filepath.write_text(content or json.dumps(entries))
    return filepath


def entry(
    *,
    ts: str = "2017-08-11T13:00:16Z",
    ms_played: int = 60_000,
    track_uri: str | None = "spotify:track:track1",
    name: str | None = "Song Name",
    artist: str | None = "Artist Name",
    album: str | None = "Album Name",
) -> dict[str, Any]:
    return {
        "ts": ts,
        "ms_played": ms_played,
        "spotify_track_uri": track_uri,
        "master_metadata_track_name": name,
        "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": album,
    }


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
    def use_case(self, mock_track_repository: mock.AsyncMock) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(track_repository=mock_track_repository)

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    entry(track_uri="spotify:track:track1"),
                    entry(track_uri="spotify:track:track2", ms_played=25_000),  # below min duration
                    entry(track_uri="spotify:track:track3"),
                    entry(track_uri=None),  # missing URI
                    entry(track_uri="spotify:episode:ep1"),  # not a track
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
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_track_repository.bulk_upsert.return_value = ([], 2)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path, min_ms_played=30_000),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=5,
            items_skipped_no_ts=0,
            items_skipped_duration=1,
            items_skipped_no_uri=2,
            unique_track_ids=2,
            tracks_already_known=0,
            tracks_played_at_updated=0,
            tracks_created=2,
            tracks_purged=0,
        )
        assert mock_track_repository.purge.call_count == 0

    @pytest.mark.parametrize(
        "json_file",
        [{"entries": [entry(track_uri="spotify:track:track1"), entry(track_uri="spotify:track:track2")]}],
        indirect=True,
    )
    async def test__tracks_built_from_file_metadata(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_track_repository.bulk_upsert.return_value = ([], 2)

        await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        assert len(upserted) == 2
        upserted_by_id = {t.provider_id: t for t in upserted}

        track1 = upserted_by_id["track1"]
        assert track1.name == "Song Name"
        assert track1.artists == ["Artist Name"]
        assert track1.album_name == "Album Name"
        assert track1.user_id == user.id
        assert track1.provider == MusicProvider.SPOTIFY

    @pytest.mark.parametrize(
        "json_file",
        [{"entries": [entry(track_uri="spotify:track:track1"), entry(track_uri="spotify:track:track2")]}],
        indirect=True,
    )
    async def test__filter__already_known(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track1 = TrackFactory.build(provider_id="track1", user_id=user.id, provider=MusicProvider.SPOTIFY)
        track2 = TrackFactory.build(provider_id="track2", user_id=user.id, provider=MusicProvider.SPOTIFY)

        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track1", "track2"])
        mock_track_repository.get_list.return_value = [track1, track2]
        mock_track_repository.bulk_upsert.return_value = ([], 0)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.tracks_already_known == 2
        assert report.tracks_played_at_updated == 2
        assert report.tracks_created == 0
        get_list_call = mock_track_repository.get_list.call_args
        assert set(get_list_call.kwargs["provider_ids"]) == {"track1", "track2"}

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {**entry(track_uri="spotify:track:track1"), "ts": None},
                    entry(track_uri="spotify:track:track2"),
                    {**entry(track_uri="spotify:track:track3"), "ts": None},
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
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track2"])
        mock_track_repository.get_list.return_value = [TrackFactory.build(provider_id="track2", user_id=user.id)]
        mock_track_repository.bulk_upsert.return_value = ([], 0)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.items_read == 3
        assert report.items_skipped_no_ts == 2
        assert report.unique_track_ids == 1

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    entry(track_uri="spotify:track:track1", ms_played=100),
                    entry(track_uri="spotify:track:track2", ms_played=200),
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
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path, min_ms_played=30_000),
        )

        assert report.items_read == 2
        assert report.items_skipped_duration == 2
        assert report.unique_track_ids == 0
        mock_track_repository.get_known_provider_ids.assert_not_called()

    @pytest.mark.parametrize(
        "json_file",
        [{"entries": [entry(track_uri="spotify:track:track1", name=None)]}],
        indirect=True,
    )
    async def test__filter__no_track_name(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.items_skipped_no_uri == 1
        assert report.unique_track_ids == 0

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
                    entry(track_uri="spotify:track:track1"),
                    entry(track_uri="spotify:track:track2"),
                    entry(track_uri="spotify:track:track3"),
                ],
            },
        ],
        indirect=True,
    )
    async def test__batch_size__chunks_upserts(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_track_repository.bulk_upsert.side_effect = [([], 1), ([], 1), ([], 1)]

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path, batch_size=1),
        )

        assert report.tracks_created == 3
        assert mock_track_repository.bulk_upsert.call_count == 3

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    # track1: appears 3x — newest ts wins
                    {**entry(track_uri="spotify:track:track1"), "ts": "2023-01-02T10:00:00Z"},
                    {**entry(track_uri="spotify:track:track1"), "ts": "2023-01-03T10:00:00Z"},
                    {**entry(track_uri="spotify:track:track1"), "ts": "2023-01-01T10:00:00Z"},
                    # track2: one valid, one missing ts (skipped)
                    {**entry(track_uri="spotify:track:track2"), "ts": "2023-01-01T10:00:00Z"},
                    {**entry(track_uri="spotify:track:track2"), "ts": None},
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
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track1", "track2"])
        mock_track_repository.get_list.return_value = [
            TrackFactory.build(provider_id="track1", user_id=user.id),
            TrackFactory.build(provider_id="track2", user_id=user.id),
        ]
        mock_track_repository.bulk_upsert.return_value = ([], 0)

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
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        build_json_file(
            filepath=tmp_path / "file1.json",
            entries=[
                {**entry(track_uri="spotify:track:track_1"), "ts": "2023-01-01T10:00:00Z"},
                {**entry(track_uri="spotify:track:track_2"), "ts": "2023-01-05T10:00:00Z"},
                {**entry(track_uri="spotify:track:track_3"), "ts": None},
                {**entry(track_uri="spotify:track:track_4"), "ts": "2023-01-01T10:00:00Z"},
            ],
        )
        build_json_file(
            filepath=tmp_path / "file2.json",
            entries=[
                {**entry(track_uri="spotify:track:track_1"), "ts": "2023-01-03T10:00:00Z"},
                {**entry(track_uri="spotify:track:track_2"), "ts": "2023-01-04T10:00:00Z"},
                {**entry(track_uri="spotify:track:track_3"), "ts": "2023-01-02T10:00:00Z"},
                {**entry(track_uri="spotify:track:track_4"), "ts": None},
            ],
        )

        mock_track_repository.get_known_provider_ids.return_value = frozenset()
        mock_track_repository.bulk_upsert.return_value = ([], 4)

        await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        upserted_by_id = {t.provider_id: t for t in upserted}

        assert upserted_by_id["track_1"].played_at == datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_2"].played_at == datetime(2023, 1, 5, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_3"].played_at == datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track_4"].played_at == datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        "json_file",
        [
            {
                "entries": [
                    {**entry(track_uri="spotify:track:track1"), "ts": "2024-03-01T10:00:00Z"},
                    {**entry(track_uri="spotify:track:track2"), "ts": "2024-03-02T12:00:00Z"},
                ],
            },
        ],
        indirect=True,
    )
    async def test__known_tracks__played_at_refreshed(
        self,
        user: User,
        tmp_path: Path,
        json_file: Path,
        use_case: ImportStreamingHistoryUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track1 = TrackFactory.build(provider_id="track1", user_id=user.id, provider=MusicProvider.SPOTIFY)
        track2 = TrackFactory.build(provider_id="track2", user_id=user.id, provider=MusicProvider.SPOTIFY)

        mock_track_repository.get_known_provider_ids.return_value = frozenset(["track1", "track2"])
        mock_track_repository.get_list.return_value = [track1, track2]
        mock_track_repository.bulk_upsert.return_value = ([], 0)

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.tracks_played_at_updated == 2
        assert report.tracks_created == 0

        upserted: list[Track] = mock_track_repository.bulk_upsert.call_args.kwargs["tracks"]
        upserted_by_id = {t.provider_id: t for t in upserted}
        assert upserted_by_id["track1"].played_at == datetime(2024, 3, 1, 10, 0, 0, tzinfo=UTC)
        assert upserted_by_id["track2"].played_at == datetime(2024, 3, 2, 12, 0, 0, tzinfo=UTC)
