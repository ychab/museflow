import asyncio
import itertools
import logging
from datetime import UTC
from datetime import datetime
from typing import cast

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import record_llm_usage
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.exceptions import TasteProfileBuildError
from museflow.domain.exceptions import TasteProfileBuildPausedError
from museflow.domain.exceptions import TasteProfileNoSeedError
from museflow.domain.exceptions import TasteProfilerRateLimitExceededError

logger = logging.getLogger(__name__)


def _split_batches(tracks: list[Track], batch_size: int) -> list[list[Track]]:
    """Splits the tracks into batches, folding a trailing batch of less than half a batch into the previous one.

    Every batch weighs the same in the merge: a few trailing tracks would otherwise replace the current vibe and add
    an era of their own.
    """
    batches = [list(batch) for batch in itertools.batched(tracks, batch_size, strict=False)]
    if len(batches) > 1 and len(batches[-1]) < batch_size / 2:
        batches[-2].extend(batches.pop())
    return batches


class BuildTasteProfileUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        profiler: TasteProfilerPort,
    ) -> None:
        self._uow = uow
        self._profiler = profiler

    async def build_profile(self, user: User, config: BuildTasteProfileConfigInput) -> TasteProfile:
        # What the profiler spent is saved whatever the outcome: a paused build was billed too.
        try:
            profile = await self._build_profile(user, config)
        finally:
            await record_llm_usage(
                user_id=user.id,
                operation=LLMOperation.TASTE_BUILD,
                usages=self._profiler.usages,
                uow=self._uow,
                profile_name=config.name,
            )
        return profile

    async def _build_profile(self, user: User, config: BuildTasteProfileConfigInput) -> TasteProfile:
        # Select the most-listened tracks as seeds (best signal quality)
        async with self._uow as uow:
            tracks = await uow.tracks.get_list(
                user_id=user.id,
                min_score=0 if config.rated_only else None,
                order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
                limit=config.track_limit,
            )
        if not tracks:
            raise TasteProfileNoSeedError(f"No tracks found for user {user.id}")

        # Re-sort chronologically so the LLM builds coherent taste eras from date-range batches.
        max_dt = datetime.max.replace(tzinfo=UTC)
        tracks = sorted(tracks, key=lambda t: t.played_at_last or max_dt)
        logger.debug(f"Taste profile seeds: {len(tracks)} tracks (most played, chronological order)")

        batches = _split_batches(tracks, config.batch_size)

        # Load checkpoint if resuming
        start_batch_index = 0
        current_profile: TasteProfileData | None = None
        if config.resume:
            async with self._uow as uow:
                checkpoint = await uow.taste_profiles.get_checkpoint(user.id, config.name)
            if checkpoint is not None:
                current_profile, start_batch_index = checkpoint
                logger.info(f"Resuming taste profile from batch {start_batch_index + 1} / {len(batches)}")
            else:
                logger.warning("No checkpoint found for this profile, starting from scratch")

        # Index of the step in progress; len(batches) denotes the final reflection step.
        step = start_batch_index + 1
        try:
            for i, batch in enumerate(batches, start=1):
                if i <= start_batch_index:
                    continue

                step = i
                logger.info(
                    f"Processing taste profile batch {i} "
                    f"({sum(len(done) for done in batches[:i])} / {len(tracks)} tracks)"
                )

                segment = await self._profiler.build_profile_segment(batch)
                current_profile = (
                    segment
                    if current_profile is None
                    else await self._profiler.merge_profiles(current_profile, segment)
                )

                # One block per batch: a paid batch survives a later failure.
                async with self._uow as uow:
                    await uow.taste_profiles.upsert_checkpoint(
                        user_id=user.id,
                        name=config.name,
                        logic_version=self._profiler.logic_version,
                        profiler_metadata=self._profiler.profiler_metadata,
                        tracks_count=len(tracks),
                        profile_data=current_profile,
                        batch_index=i,
                    )

                if config.throttling_sleep_seconds > 0 and i < len(batches):
                    logger.debug(f"Throttling: sleeping {config.throttling_sleep_seconds}s before next batch")
                    await asyncio.sleep(config.throttling_sleep_seconds)

            # The merged profile is already checkpointed: a reflection failure is resumable too.
            step = len(batches)
            logger.info("Processing psychographic reflection")
            current_profile = await self._profiler.reflect_on_profile(cast(TasteProfileData, current_profile))
        except (TasteProfilerRateLimitExceededError, TasteProfileBuildError) as e:
            # The caller reports the pause from the exception: a warning here would print it twice
            logger.debug(
                f"Taste profile build failed at step {step} / {len(batches)}, pausing build: {e}",
                extra={"step": step, "total": len(batches)},
            )
            raise TasteProfileBuildPausedError(step, len(batches), reason=str(e)) from e

        taste_profile = TasteProfile(
            user_id=user.id,
            name=config.name,
            profile=current_profile,
            profiler_metadata=self._profiler.profiler_metadata,
            tracks_count=len(tracks),
            logic_version=self._profiler.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ).sort_timeline()

        async with self._uow as uow:
            return await uow.taste_profiles.upsert(taste_profile)
