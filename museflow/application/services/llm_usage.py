import logging
import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
from museflow.domain.value_objects.llm import LLMUsage

logger = logging.getLogger(__name__)


async def record_llm_usage(
    user_id: uuid.UUID,
    operation: LLMOperation,
    usages: list[LLMUsage],
    uow: UnitOfWorkPort,
    profile_name: str | None = None,
    playlist_id: uuid.UUID | None = None,
) -> None:
    """Saves what one run spent, in a transaction of its own; meant for a `finally:` block.

    A failure is logged and never raised, so it cannot hide the outcome of the run. The profile stays unknown when no
    profile has that name yet, e.g. a build paused before its first checkpoint.
    """
    if not usages:
        return

    run_id = uuid.uuid4()
    try:
        async with uow:
            profile = await uow.taste_profiles.get(user_id=user_id, name=profile_name) if profile_name else None
            await uow.llm_usage.bulk_create(
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
    except Exception:
        logger.exception("Failed to save the LLM usage", extra={"user_id": str(user_id), "operation": operation.value})
