import uuid
from dataclasses import dataclass

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.value_objects.llm import LLMUsage


@dataclass(frozen=True, kw_only=True)
class ImportLLMUsageResult:
    imported_count: int
    skipped_count: int


async def import_llm_usage(
    user_id: uuid.UUID,
    entries: list[LLMUsageEntryInput],
    uow: UnitOfWorkPort,
) -> ImportLLMUsageResult:
    # One block: the import is saved as a whole, or not at all.
    async with uow:
        # A run has one row per step and model: a row already there is skipped, so importing twice adds nothing.
        keys = {
            (record.run_id, record.usage.step, record.usage.model)
            for record in await uow.llm_usage.get_list(user_id=user_id)
        }
        profile_ids = {profile.name: profile.id for profile in await uow.taste_profiles.get_list(user_id=user_id)}

        records: list[LLMUsageRecord] = []
        for entry in entries:
            key = (entry.run_id, entry.step, entry.model)
            if key in keys:
                continue
            keys.add(key)
            records.append(
                LLMUsageRecord(
                    user_id=user_id,
                    run_id=entry.run_id,
                    operation=entry.operation,
                    usage=LLMUsage(
                        step=entry.step,
                        model=entry.model,
                        calls=entry.calls,
                        prompt_tokens=entry.prompt_tokens,
                        completion_tokens=entry.completion_tokens,
                        reasoning_tokens=entry.reasoning_tokens,
                        cost=entry.cost,
                        duration=entry.duration,
                    ),
                    # The profile link survives when a profile of that name was imported first.
                    profile_id=profile_ids.get(entry.profile_name) if entry.profile_name else None,
                    created_at=entry.created_at,
                )
            )

        if records:
            await uow.llm_usage.bulk_create(records)

    return ImportLLMUsageResult(imported_count=len(records), skipped_count=len(entries) - len(records))
