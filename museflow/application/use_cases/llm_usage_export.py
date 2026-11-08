import uuid

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort


async def export_llm_usage(
    user_id: uuid.UUID,
    uow: UnitOfWorkPort,
) -> list[LLMUsageEntryInput]:
    async with uow:
        records = await uow.llm_usage.get_list(user_id=user_id)
        profiles = await uow.taste_profiles.get_list(user_id=user_id)

    profile_names = {profile.id: profile.name for profile in profiles}

    # The entries have the shape the import reads, so an export always imports back.
    return [
        LLMUsageEntryInput(
            run_id=record.run_id,
            operation=record.operation,
            profile_name=profile_names.get(record.profile_id) if record.profile_id else None,
            step=record.usage.step,
            model=record.usage.model,
            calls=record.usage.calls,
            prompt_tokens=record.usage.prompt_tokens,
            completion_tokens=record.usage.completion_tokens,
            reasoning_tokens=record.usage.reasoning_tokens,
            cost=record.usage.cost,
            duration=record.usage.duration,
            created_at=record.created_at,
        )
        for record in records
    ]
