import logging
import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
from museflow.domain.value_objects.llm import LLMUsage

logger = logging.getLogger(__name__)


class LLMUsageService:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    async def add_all(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        operation: LLMOperation,
        usages: list[LLMUsage],
        profile_name: str | None = None,
        playlist_id: uuid.UUID | None = None,
        *,
        uow: UnitOfWorkPort,
    ) -> None:
        """Adds what a batch spent to its run, in the open block of the batch: the batch and its cost commit together.

        The profile stays unknown when no profile has that name yet, e.g. a build paused before its first checkpoint;
        a later batch of the run links it.
        """
        profile = await uow.taste_profiles.get(user_id=user_id, name=profile_name) if profile_name else None
        await uow.llm_usage.bulk_accumulate(
            [
                LLMUsageRecord(
                    user_id=user_id,
                    run_id=run_id,
                    operation=operation,
                    usage=usage,
                    profile_id=profile.id if profile else None,
                    playlist_id=playlist_id,
                )
                for usage in usages
            ]
        )

    async def save(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        operation: LLMOperation,
        usages: list[LLMUsage],
        profile_name: str | None = None,
        playlist_id: uuid.UUID | None = None,
    ) -> None:
        """Adds what the run spent since its last batch, in a transaction of its own; meant for a `finally:` block.

        A failure is logged and never raised, so it cannot hide the outcome of the run.
        """
        try:
            async with self._uow as uow:
                await self.add_all(user_id, run_id, operation, usages, profile_name, playlist_id, uow=uow)
        except Exception:
            logger.exception(
                "Failed to save the LLM usage", extra={"user_id": str(user_id), "operation": operation.value}
            )
