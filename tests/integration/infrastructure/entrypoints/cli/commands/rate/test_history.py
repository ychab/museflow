from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.entrypoints.cli.commands.rate.history import rate_history_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateHistoryLogic:
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

        await rate_history_logic(email=user.email, limit=10, reset=False)

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

        await rate_history_logic(email=user.email, limit=10, reset=False, artist="Radiohead")

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
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=None)
        mock_typer_prompt.return_value = "8"
        mock_typer_confirm.return_value = False

        with mock.patch.object(SpotifyLibraryAdapter, "play_track", new_callable=mock.AsyncMock) as mock_play:
            await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        mock_play.assert_awaited_once_with(track_db.provider_links[0]["provider_id"])

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 8
