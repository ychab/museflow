import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Row
from sqlalchemy import Select
from sqlalchemy import SQLColumnExpression
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
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

    async def get_list(self, user_id: uuid.UUID) -> list[LLMUsageRecord]:
        stmt = (
            select(LLMUsageModel)
            .where(LLMUsageModel.user_id == user_id)
            .order_by(LLMUsageModel.created_at, LLMUsageModel.run_id, LLMUsageModel.step, LLMUsageModel.model)
        )
        return [row.to_entity() for row in (await self.session.execute(stmt)).scalars()]

    async def bulk_create(self, records: list[LLMUsageRecord]) -> None:
        self.session.add_all([LLMUsageModel.from_entity(record) for record in records])
        await self.session.flush()

    async def summarize(
        self,
        user_id: uuid.UUID | None,
        group_by: list[LLMUsageGroupBy],
        operation: LLMOperation | None = None,
        since: date | None = None,
        until: date | None = None,
    ) -> LLMUsageSummary:
        dimensions = [self._dimension(grouping, all_users=user_id is None) for grouping in group_by]

        # Level by level: the level's own order first, then its keys, so the rows of a group stay together.
        keys: list[SQLColumnExpression[object]] = []
        order_by: list[SQLColumnExpression[object]] = []
        for grouping, dimension in zip(group_by, dimensions, strict=True):
            keys = [*keys, *dimension.keys]
            order_by += [self._level_order(grouping, dimension, keys), *dimension.keys]

        groups_stmt: Select[*tuple[Any, ...]] = (
            select(
                *[dimension.value.label(f"value_{index}") for index, dimension in enumerate(dimensions)],
                *self._sums(),
            )
            .select_from(LLMUsageModel)
            .join(UserModel, UserModel.id == LLMUsageModel.user_id)
            .outerjoin(TasteProfileModel, TasteProfileModel.id == LLMUsageModel.profile_id)
            .group_by(*keys)
            .order_by(*order_by)
        )
        # The total runs its own query: a run spanning several groups counts once, and it exists without any usage.
        total_stmt = select(*self._sums()).select_from(LLMUsageModel)

        filters = self._filters(user_id, operation, since, until)
        groups = (await self.session.execute(groups_stmt.where(*filters))).all()
        total = (await self.session.execute(total_stmt.where(*filters))).one()
        return LLMUsageSummary(
            groups=[
                LLMUsageGroup(
                    values=[self._value(getattr(row, f"value_{index}")) for index in range(len(dimensions))],
                    totals=self._totals(row),
                )
                for row in groups
            ],
            total=self._totals(total),
        )

    def _dimension(self, group_by: LLMUsageGroupBy, all_users: bool) -> _Dimension:
        if group_by == LLMUsageGroupBy.RUN:
            # The rows of a run are saved together: the first one dates it.
            started_at = func.to_char(
                func.timezone("UTC", func.min(LLMUsageModel.created_at)), "YYYY-MM-DD HH24:MI:SS"
            )
            return _Dimension(keys=[LLMUsageModel.run_id], value=started_at)

        # Profile names are unique per user only: across users, the email tells two "evening" profiles apart.
        # `||` gives NULL without a profile, so these runs still fall in the "no profile" group.
        profile = UserModel.email + " / " + TasteProfileModel.name if all_users else TasteProfileModel.name
        columns: dict[LLMUsageGroupBy, SQLColumnExpression[object]] = {
            LLMUsageGroupBy.OPERATION: LLMUsageModel.operation,
            LLMUsageGroupBy.MODEL: LLMUsageModel.model,
            LLMUsageGroupBy.EFFORT: LLMUsageModel.reasoning_effort,
            LLMUsageGroupBy.STEP: LLMUsageModel.step,
            LLMUsageGroupBy.MONTH: func.to_char(func.timezone("UTC", LLMUsageModel.created_at), "YYYY-MM"),
            LLMUsageGroupBy.PROFILE: profile,
            LLMUsageGroupBy.USER: UserModel.email,
        }
        return _Dimension(keys=[columns[group_by]], value=columns[group_by])

    def _level_order(
        self,
        group_by: LLMUsageGroupBy,
        dimension: _Dimension,
        partition: list[SQLColumnExpression[object]],
    ) -> SQLColumnExpression[object]:
        """Orders a level of the groups: `partition` holds the keys of this level and the levels above."""
        if group_by == LLMUsageGroupBy.MONTH:
            return dimension.value
        if group_by == LLMUsageGroupBy.RUN:
            return func.min(func.min(LLMUsageModel.created_at)).over(partition_by=partition)
        return func.sum(func.sum(LLMUsageModel.cost)).over(partition_by=partition).desc()

    def _filters(
        self,
        user_id: uuid.UUID | None,
        operation: LLMOperation | None,
        since: date | None,
        until: date | None,
    ) -> list[SQLColumnExpression[bool]]:
        filters: list[SQLColumnExpression[bool]] = []
        if user_id is not None:
            filters.append(LLMUsageModel.user_id == user_id)
        if operation is not None:
            filters.append(LLMUsageModel.operation == operation)
        if since is not None:
            filters.append(LLMUsageModel.created_at >= datetime.combine(since, time.min, tzinfo=UTC))
        if until is not None:
            # Up to the end of the day: before the next day starts.
            filters.append(
                LLMUsageModel.created_at < datetime.combine(until + timedelta(days=1), time.min, tzinfo=UTC)
            )
        return filters

    def _sums(self) -> list[SQLColumnExpression[object]]:
        return [
            func.count(distinct(LLMUsageModel.run_id)).label("runs"),
            func.coalesce(func.sum(LLMUsageModel.calls), 0).label("calls"),
            func.coalesce(func.sum(LLMUsageModel.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LLMUsageModel.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LLMUsageModel.reasoning_tokens), 0).label("reasoning_tokens"),
            func.coalesce(func.sum(LLMUsageModel.cost), 0).label("cost"),
            func.coalesce(func.sum(LLMUsageModel.duration), timedelta(0)).label("duration"),
        ]

    def _value(self, value: object) -> str | None:
        # Enum columns come back as their StrEnum members, which read as their values.
        return None if value is None else str(value)

    def _totals(self, row: Row[*tuple[Any, ...]]) -> LLMUsageTotals:
        return LLMUsageTotals(
            runs=row.runs,
            calls=row.calls,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            reasoning_tokens=row.reasoning_tokens,
            cost=Decimal(row.cost),
            duration=row.duration,
        )


@dataclass(frozen=True, kw_only=True)
class _Dimension:
    keys: list[SQLColumnExpression[object]]  # the columns to group on
    value: SQLColumnExpression[object]  # the value shown for the group
