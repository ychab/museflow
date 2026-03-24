import json
from pathlib import Path
from typing import Any
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryUseCase
from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter

from tests import ASSETS_DIR
from tests.integration.factories.models.music import TrackModelFactory
from tests.integration.utils.wiremock import WireMockContext

HISTORY_DIR: Final[Path] = ASSETS_DIR / "history"


@pytest.mark.wiremock("spotify")
class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def tracks_json_response(self) -> dict[str, Any]:
        return {
            "tracks": [
                json.loads((ASSETS_DIR / "wiremock" / "spotify" / "__files" / f"track_{track_id}.json").read_text())
                for track_id in [
                    # Same ID's as the history JSON files.
                    "6wb6zxkNTBtcYVkXcvNyJp",
                    "76v0OHTbZGeOZYmaLtEDhQ",
                    "5BuWeANxxuVOZdTCgnaOnp",
                    "4BqYFb5LHhRmmTDsPyUmQg",
                ]
            ],
        }

    @pytest.fixture
    def use_case(
        self,
        spotify_library: SpotifyLibraryAdapter,
        track_repository: TrackRepository,
    ) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(
            provider_library=spotify_library,
            track_repository=track_repository,
        )

    async def test__nominal__fetch_single(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        spotify_wiremock: WireMockContext,
    ) -> None:
        """
        Streaming_History_Audio_2017-2018_1.json : read=3, skip_dur=1, skip_uri=0 → 2 ids
        Streaming_History_Audio_2023-2024_11.json: read=3, skip_dur=1, skip_uri=0 → 2 ids
        Total: read=6, skip_dur=2, skip_uri=0, unique_track_ids=4
        """
        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=HISTORY_DIR,
                min_ms_played=30_000,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=6,
            items_skipped_duration=2,
            items_skipped_no_uri=0,
            unique_track_ids=4,
            tracks_already_known=0,
            tracks_fetched=4,
            tracks_created=4,
            tracks_purged=0,
        )

    async def test__nominal__fetch_bulk(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        tracks_json_response: dict[str, Any],
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/tracks",
            status=200,
            json_body=tracks_json_response,
        )

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=HISTORY_DIR,
                min_ms_played=30_000,
                batch_size=50,
                fetch_bulk=True,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=6,
            items_skipped_duration=2,
            items_skipped_no_uri=0,
            unique_track_ids=4,
            tracks_already_known=0,
            tracks_fetched=4,
            tracks_created=4,
            tracks_purged=0,
        )

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        spotify_wiremock: WireMockContext,
    ) -> None:
        # Create 3 HISTORY tracks for the user to purge.
        tracks = await TrackModelFactory.create_batch_async(
            size=3,
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            sources=int(TrackSource.HISTORY),
        )
        track_ids = [track.id for track in tracks]

        report = await use_case.import_history(
            user=user,
            config=ImportStreamingHistoryConfigInput(
                directory=HISTORY_DIR,
                purge=True,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=6,
            items_skipped_duration=2,
            items_skipped_no_uri=0,
            unique_track_ids=4,
            tracks_already_known=0,
            tracks_fetched=4,
            tracks_created=4,
            tracks_purged=3,
        )

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.id.in_(track_ids))
        count = (await async_session_db.execute(stmt)).scalar()
        assert count == 0
