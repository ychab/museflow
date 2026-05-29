from typing import Any

from pydantic import TypeAdapter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel
from museflow.infrastructure.entrypoints.cli.commands.taste.import_ import import_logic

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestTasteImportLogic:
    async def test__nominal(self, user: User, async_session_db: AsyncSession) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        profile_data: dict[str, Any] = TypeAdapter(TasteProfile).dump_python(taste_profile_db.to_entity(), mode="json")

        result = await import_logic(email=user.email, data=profile_data)

        assert isinstance(result, TasteProfile)
        assert result.name == "my-profile"
        assert result.user_id == user.id

        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user.id,
            TasteProfileModel.name == "my-profile",
        )
        saved_db = (await async_session_db.execute(stmt)).scalar_one_or_none()
        assert saved_db is not None

    async def test__reimport_overwrites(self, user: User, async_session_db: AsyncSession) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        original_tracks_count = taste_profile_db.to_entity().tracks_count
        profile_data: dict[str, Any] = TypeAdapter(TasteProfile).dump_python(taste_profile_db.to_entity(), mode="json")

        await import_logic(email=user.email, data=profile_data)

        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user.id,
            TasteProfileModel.name == "my-profile",
        )
        rows = (await async_session_db.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].tracks_count == original_tracks_count
