from collections.abc import Iterable
from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.entrypoints.cli.commands.rate.history import rate_history_logic
from museflow.infrastructure.entrypoints.cli.commands.rate.history import rate_history_reset_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateHistoryLogic:
    @pytest.fixture
    def mock_play_track(self) -> Iterable[mock.AsyncMock]:
        with mock.patch.object(SpotifyLibraryAdapter, "play_track", new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=None)
        mock_typer_prompt.return_value = "8"
        mock_typer_confirm.return_value = False

        await rate_history_logic(email=user.email, limit=10)

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 8

    async def test__artist_filter__rates_only_matching_tracks(
        self,
        async_session_db: AsyncSession,
        user: User,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        target_db = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, artists=["Radiohead"]
        )
        other_db = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, artists=["Other Artist"]
        )
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_history_logic(email=user.email, limit=10, artist="Radiohead")

        stmt_target = select(TrackModel).where(TrackModel.id == target_db.id)
        stmt_other = select(TrackModel).where(TrackModel.id == other_db.id)
        updated_target = (await async_session_db.execute(stmt_target)).scalar_one()
        updated_other = (await async_session_db.execute(stmt_other)).scalar_one()
        assert updated_target.score == 7
        assert updated_other.score is None

    async def test__nominal__play(
        self,
        async_session_db: AsyncSession,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
        mock_play_track: mock.AsyncMock,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=None)
        mock_typer_prompt.return_value = "8"
        mock_typer_confirm.return_value = False

        await rate_history_logic(email=user.email, limit=10, provider=MusicProvider.SPOTIFY)

        mock_play_track.assert_awaited_once_with(track_db.provider_links[0]["provider_id"])

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 8


class TestRateHistoryResetLogic:
    async def test__nominal(self, async_session_db: AsyncSession, user: User) -> None:
        history_dbs = [
            await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=score)
            for score in (4, 9)
        ]
        library_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=7)

        count = await rate_history_reset_logic(email=user.email)

        assert count == 2
        stmt = select(TrackModel.id, TrackModel.score).where(TrackModel.user_id == user.id)
        scores = {track_id: score for track_id, score in (await async_session_db.execute(stmt)).all()}
        assert all(scores[track_db.id] is None for track_db in history_dbs)
        assert scores[library_db.id] == 7
