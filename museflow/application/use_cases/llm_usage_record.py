import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
from museflow.domain.value_objects.llm import LLMUsage


async def record_llm_usage(
    user_id: uuid.UUID,
    operation: LLMOperation,
    usages: list[LLMUsage],
    uow: UnitOfWorkPort,
    profile_name: str | None = None,
    playlist_id: uuid.UUID | None = None,
) -> None:
    """Saves what one command run spent, in its own transaction so that it survives the command's failure.

    The profile is found by name, else through the playlist (a discovery on the latest profile). It stays unknown
    when a build paused before its first checkpoint, or when a discovery without a name made no playlist.
    """
    if not usages:
        return

    run_id = uuid.uuid4()
    async with uow:
        profile_id: uuid.UUID | None = None
        if profile_name is not None:
            profile = await uow.taste_profiles.get(user_id=user_id, name=profile_name)
            profile_id = profile.id if profile else None
        elif playlist_id is not None:
            playlist = await uow.playlists.get(user_id=user_id, playlist_id=playlist_id)
            profile_id = playlist.profile_id if playlist else None

        await uow.llm_usage.add_many(
            [
                LLMUsageRecord(
                    user_id=user_id,
                    run_id=run_id,
                    operation=operation,
                    usage=usage,
                    profile_id=profile_id,
                    playlist_id=playlist_id,
                )
                for usage in usages
            ]
        )
