import asyncio
import logging
import math
from datetime import UTC
from datetime import datetime
from typing import cast

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import record_llm_usage
from museflow.domain.const import TASTE_BATCH_COUNT_TARGET
from museflow.domain.const import TASTE_BATCH_SIZE_MIN
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.exceptions import TasteProfileBuildError
from museflow.domain.exceptions import TasteProfileBuildPausedError
from museflow.domain.exceptions import TasteProfileNoSeedError
from museflow.domain.exceptions import TasteProfilerRateLimitExceededError

logger = logging.getLogger(__name__)


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
        # Cut the listening history into periods holding the same number of plays, each seeded with the tracks most
        # played in it: a period is described by what was listened to then, a track replayed years later in each.
        min_score = 0 if config.rated_only else None
        async with self._uow as uow:
            played_tracks = await uow.track_plays.count_played_tracks(user_id=user.id, min_score=min_score)
        seeds = min(config.track_limit, played_tracks)
        if not seeds:
            raise TasteProfileNoSeedError(f"No played tracks found for user {user.id}")

        tracks_per_period = config.batch_size or max(TASTE_BATCH_SIZE_MIN, math.ceil(seeds / TASTE_BATCH_COUNT_TARGET))
        async with self._uow as uow:
            periods = await uow.track_plays.get_periods(
                user_id=user.id,
                periods=math.ceil(seeds / tracks_per_period),
                tracks_per_period=tracks_per_period,
                min_score=min_score,
            )
        tracks_count = sum(len(period.tracks) for period in periods)
        logger.debug(
            f"Taste profile periods: {len(periods)} of up to {tracks_per_period} tracks ({tracks_count} seeds)"
        )

        # Load checkpoint if resuming
        start_batch_index = 0
        current_profile: TasteProfileData | None = None
        if config.resume:
            async with self._uow as uow:
                checkpoint = await uow.taste_profiles.get_checkpoint(user.id, config.name)
            if checkpoint is not None:
                current_profile, start_batch_index = checkpoint
                logger.info(f"Resuming taste profile from period {start_batch_index + 1} / {len(periods)}")
            else:
                logger.warning("No checkpoint found for this profile, starting from scratch")

        # Index of the step in progress; len(periods) denotes the final reflection step.
        step = start_batch_index + 1
        try:
            for i, period in enumerate(periods, start=1):
                if i <= start_batch_index:
                    continue

                step = i
                logger.info(
                    f"Processing taste profile period {i} / {len(periods)} "
                    f"({period.start.date()} to {period.end.date()}, {len(period.tracks)} tracks)"
                )

                segment = await self._profiler.build_profile_segment(period)
                # Weighted by plays, the core identity is the mean over the listening so far, whatever the period size
                plays_processed = sum(done.plays for done in periods[:i])
                current_profile = (
                    segment
                    if current_profile is None
                    else await self._profiler.merge_profiles(current_profile, segment, period.plays / plays_processed)
                )

                # One block per batch: a paid batch survives a later failure.
                async with self._uow as uow:
                    await uow.taste_profiles.upsert_checkpoint(
                        user_id=user.id,
                        name=config.name,
                        logic_version=self._profiler.logic_version,
                        profiler_metadata=self._profiler.profiler_metadata,
                        tracks_count=tracks_count,
                        profile_data=current_profile,
                        batch_index=i,
                    )

                if config.throttling_sleep_seconds > 0 and i < len(periods):
                    logger.debug(f"Throttling: sleeping {config.throttling_sleep_seconds}s before next batch")
                    await asyncio.sleep(config.throttling_sleep_seconds)

            # The merged profile is already checkpointed: a reflection failure is resumable too.
            step = len(periods)
            logger.info("Processing psychographic reflection")
            current_profile = await self._profiler.reflect_on_profile(cast(TasteProfileData, current_profile))
        except (TasteProfilerRateLimitExceededError, TasteProfileBuildError) as e:
            # The caller reports the pause from the exception: a warning here would print it twice
            logger.debug(
                f"Taste profile build failed at step {step} / {len(periods)}, pausing build: {e}",
                extra={"step": step, "total": len(periods)},
            )
            raise TasteProfileBuildPausedError(step, len(periods), reason=str(e)) from e

        taste_profile = TasteProfile(
            user_id=user.id,
            name=config.name,
            profile=current_profile,
            profiler_metadata=self._profiler.profiler_metadata,
            tracks_count=tracks_count,
            logic_version=self._profiler.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ).sort_timeline()

        async with self._uow as uow:
            return await uow.taste_profiles.upsert(taste_profile)
