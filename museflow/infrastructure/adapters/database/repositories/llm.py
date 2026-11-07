import uuid
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from decimal import Decimal

from sqlalchemy import Row
from sqlalchemy import Select
from sqlalchemy import SQLColumnExpression
from sqlalchemy import String
from sqlalchemy import cast
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.value_objects.llm import LLMUsageGroup
from museflow.domain.value_objects.llm import LLMUsageSummary
from museflow.domain.value_objects.llm import LLMUsageTotals
from museflow.infrastructure.adapters.database.models import User as UserModel
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel


class LLMUsageSQLRepository(LLMUsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(self, records: list[LLMUsageRecord]) -> None:
        self.session.add_all([LLMUsageModel.from_entity(record) for record in records])
        await self.session.flush()

    async def summarize(
        self,
        user_id: uuid.UUID | None,
        group_by: LLMUsageGroupBy,
        since: date | None = None,
    ) -> LLMUsageSummary:
        keys, group = self._grouping(group_by, all_users=user_id is None)
        cost = func.coalesce(func.sum(LLMUsageModel.cost), 0)
        orders: dict[LLMUsageGroupBy, SQLColumnExpression[object]] = {
            LLMUsageGroupBy.MONTH: group,
            LLMUsageGroupBy.RUN: func.min(LLMUsageModel.created_at),
        }

        # ROLLUP appends the grand total row, sorted last by GROUPING(): it counts the distinct runs over all groups.
        stmt: Select[object, int, int, int, int, int, Decimal] = (
            select(
                group.label("name"),
                func.count(distinct(LLMUsageModel.run_id)).label("runs"),
                func.coalesce(func.sum(LLMUsageModel.calls), 0).label("calls"),
                func.coalesce(func.sum(LLMUsageModel.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMUsageModel.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMUsageModel.reasoning_tokens), 0).label("reasoning_tokens"),
                cost.label("cost"),
            )
            .select_from(LLMUsageModel)
            .join(UserModel, UserModel.id == LLMUsageModel.user_id)
            .outerjoin(TasteProfileModel, TasteProfileModel.id == LLMUsageModel.profile_id)
            .group_by(func.rollup(tuple_(*keys)))
            .order_by(
                func.grouping(keys[0]),
                orders.get(group_by, cost.desc()),
                group,
            )
        )
        if user_id is not None:
            stmt = stmt.where(LLMUsageModel.user_id == user_id)
        if since is not None:
            stmt = stmt.where(LLMUsageModel.created_at >= datetime.combine(since, time.min, tzinfo=UTC))

        rows = (await self.session.execute(stmt)).all()
        # The total row comes last, and always exists: ROLLUP returns it even without any usage.
        return LLMUsageSummary(
            groups=[
                LLMUsageGroup(name=None if row.name is None else str(row.name), totals=self._totals(row))
                for row in rows[:-1]
            ],
            total=self._totals(rows[-1]),
        )

    def _grouping(
        self,
        group_by: LLMUsageGroupBy,
        all_users: bool,
    ) -> tuple[list[SQLColumnExpression[object]], SQLColumnExpression[object]]:
        """Returns the columns to group on, and the group name built from them."""
        if group_by == LLMUsageGroupBy.RUN:
            # The operation, the profile and the user are the same on every row of a run: grouping on them too makes
            # them usable in the name. The rows of a run are saved together, so the first one dates it.
            started_at = func.to_char(
                func.timezone("UTC", func.min(LLMUsageModel.created_at)), "YYYY-MM-DD HH24:MI:SS"
            )
            # The column holds the enum names: lowercased, they are the values.
            operation = func.lower(cast(LLMUsageModel.operation, String))
            user = "(" + UserModel.email + ")" if all_users else None
            name = func.concat_ws(" ", started_at, operation, TasteProfileModel.name, user)
            return [LLMUsageModel.run_id, LLMUsageModel.operation, TasteProfileModel.name, UserModel.email], name

        # Profile names are unique per user only: across users, the email tells two "evening" profiles apart.
        # `||` gives NULL without a profile, so these runs still fall in the "no profile" group.
        profile = UserModel.email + " / " + TasteProfileModel.name if all_users else TasteProfileModel.name
        expressions: dict[LLMUsageGroupBy, SQLColumnExpression[object]] = {
            LLMUsageGroupBy.OPERATION: LLMUsageModel.operation,
            LLMUsageGroupBy.MODEL: LLMUsageModel.model,
            LLMUsageGroupBy.STEP: LLMUsageModel.step,
            LLMUsageGroupBy.MONTH: func.to_char(func.timezone("UTC", LLMUsageModel.created_at), "YYYY-MM"),
            LLMUsageGroupBy.PROFILE: profile,
            LLMUsageGroupBy.USER: UserModel.email,
        }
        return [expressions[group_by]], expressions[group_by]

    def _totals(self, row: Row[object, int, int, int, int, int, Decimal]) -> LLMUsageTotals:
        return LLMUsageTotals(
            runs=row.runs,
            calls=row.calls,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            reasoning_tokens=row.reasoning_tokens,
            cost=Decimal(row.cost),
        )
