from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.domain.types import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.rate.history import rate_history_logic

from tests.integration.factories.models.music import TrackModelFactory


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
