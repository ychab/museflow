import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.taste_build import TasteProfileBuildRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import TasteProfileBuildModel
from museflow.infrastructure.adapters.database.repositories.taste_build import TasteProfileBuildSQLRepository

from tests.integration.factories.models.taste import TasteProfileBuildModelFactory

LEASE_DURATION: Final[timedelta] = timedelta(minutes=15)


class TestTasteProfileBuildSQLRepository:
    @pytest.fixture
    def taste_build_repository(self, async_session_db: AsyncSession) -> TasteProfileBuildRepository:
        return TasteProfileBuildSQLRepository(async_session_db)

    @pytest.fixture
    async def lease_db(self, request: pytest.FixtureRequest, user: User) -> TasteProfileBuildModel:
        """The lease of another build, ending in `request.param` from now (negative: expired)."""
        lease_until = datetime.now(UTC) + timedelta(minutes=request.param)
        return await TasteProfileBuildModelFactory.create_async(user_id=user.id, lease_until=lease_until)

    async def _get_lease(self, async_session_db: AsyncSession, user: User, name: str) -> TasteProfileBuildModel | None:
        stmt = select(TasteProfileBuildModel).where(
            TasteProfileBuildModel.user_id == user.id,
            TasteProfileBuildModel.name == name,
        )
        lease_db: TasteProfileBuildModel | None = (await async_session_db.execute(stmt)).scalar_one_or_none()

        if lease_db is not None:
            await async_session_db.refresh(lease_db)

        return lease_db

    async def test__claim__free(
        self,
        async_session_db: AsyncSession,
        user: User,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        build_id = uuid.uuid4()

        claimed = await taste_build_repository.claim(user.id, "main", build_id, LEASE_DURATION)

        assert claimed is True
        lease_db = await self._get_lease(async_session_db, user, "main")
        assert lease_db is not None
        assert lease_db.build_id == build_id

    @pytest.mark.parametrize("lease_db", [10], indirect=True)
    async def test__claim__held(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        holder_id, lease_until = lease_db.build_id, lease_db.lease_until

        claimed = await taste_build_repository.claim(user.id, lease_db.name, uuid.uuid4(), LEASE_DURATION)

        assert claimed is False
        lease_db_after = await self._get_lease(async_session_db, user, lease_db.name)
        assert lease_db_after is not None
        assert (lease_db_after.build_id, lease_db_after.lease_until) == (holder_id, lease_until)

    @pytest.mark.parametrize("lease_db", [-10], indirect=True)
    async def test__claim__expired(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        build_id = uuid.uuid4()

        claimed = await taste_build_repository.claim(user.id, lease_db.name, build_id, LEASE_DURATION)

        assert claimed is True
        lease_db_after = await self._get_lease(async_session_db, user, lease_db.name)
        assert lease_db_after is not None
        assert lease_db_after.build_id == build_id
        assert lease_db_after.lease_until > datetime.now(UTC)

    @pytest.mark.parametrize("lease_db", [-10], indirect=True)
    async def test__renew__holder__even_expired(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        renewed = await taste_build_repository.renew(user.id, lease_db.name, lease_db.build_id, LEASE_DURATION)

        assert renewed is True
        lease_db_after = await self._get_lease(async_session_db, user, lease_db.name)
        assert lease_db_after is not None
        assert lease_db_after.lease_until > datetime.now(UTC)

    @pytest.mark.parametrize("lease_db", [10], indirect=True)
    async def test__renew__taken_over(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        lease_until = lease_db.lease_until

        renewed = await taste_build_repository.renew(user.id, lease_db.name, uuid.uuid4(), LEASE_DURATION)

        assert renewed is False
        lease_db_after = await self._get_lease(async_session_db, user, lease_db.name)
        assert lease_db_after is not None
        assert lease_db_after.lease_until == lease_until

    @pytest.mark.parametrize("lease_db", [10], indirect=True)
    async def test__release__holder(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        await taste_build_repository.release(user.id, lease_db.name, lease_db.build_id)

        assert await self._get_lease(async_session_db, user, lease_db.name) is None

    @pytest.mark.parametrize("lease_db", [10], indirect=True)
    async def test__release__taken_over(
        self,
        async_session_db: AsyncSession,
        user: User,
        lease_db: TasteProfileBuildModel,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        await taste_build_repository.release(user.id, lease_db.name, uuid.uuid4())

        assert await self._get_lease(async_session_db, user, lease_db.name) is not None

    @pytest.mark.parametrize(("lease_db", "expected"), [(10, True), (-10, False)], indirect=["lease_db"])
    async def test__is_held(
        self,
        user: User,
        lease_db: TasteProfileBuildModel,
        expected: bool,
        taste_build_repository: TasteProfileBuildRepository,
    ) -> None:
        assert await taste_build_repository.is_held(user.id, lease_db.name) is expected

    async def test__is_held__no_lease(self, user: User, taste_build_repository: TasteProfileBuildRepository) -> None:
        assert await taste_build_repository.is_held(user.id, "main") is False
