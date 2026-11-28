import asyncio
import logging
import math
import uuid
from datetime import UTC
from datetime import datetime
from typing import cast

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.outputs.progress import StepAdvanced
from museflow.application.outputs.progress import StepDone
from museflow.application.outputs.progress import StepResumed
from museflow.application.outputs.progress import StepStarted
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.progress import ProgressPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import LLMUsageService
from museflow.domain.const import TASTE_BATCH_COUNT_TARGET
from museflow.domain.const import TASTE_BATCH_SIZE_MIN
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import ProgressStep
from museflow.domain.exceptions import TasteProfileBuildError
from museflow.domain.exceptions import TasteProfileBuildInProgressError
from museflow.domain.exceptions import TasteProfileBuildPausedError
from museflow.domain.exceptions import TasteProfileNoSeedError
from museflow.domain.exceptions import TasteProfilerRateLimitExceededError
from museflow.domain.value_objects.taste import TasteProfileData

logger = logging.getLogger(__name__)


class BuildTasteProfileUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        profiler: TasteProfilerPort,
        progress: ProgressPort,
    ) -> None:
        self._uow = uow
        self._profiler = profiler
        self._progress = progress
        self._llm_usage = LLMUsageService(uow=uow)

    async def build_profile(self, user: User, config: BuildTasteProfileConfigInput) -> TasteProfile:
        """Builds the profile, or resumes it from its last checkpoint.

        Raises:
            TasteProfileBuildInProgressError: If another build of the profile is running, before any LLM call, or if
                another build took the profile over from this one, whose lease had expired.
        """
        # Before any paid call: two builds of one profile would pay twice and overwrite each other's checkpoints.
        build_id = uuid.uuid4()

        async with self._uow as uow:
            claimed = await uow.taste_builds.claim(
                user_id=user.id,
                name=config.name,
                build_id=build_id,
                lease_duration=config.lease_duration,
            )

        if not claimed:
            raise TasteProfileBuildInProgressError(
                f"Another build of taste profile '{config.name}' is running: wait for it to end, or for its lease to "
                f"expire if it was killed (at most {config.lease_duration})"
            )

        # What the profiler spent since the last checkpoint is saved whatever the outcome: a paused build was billed
        # too. The build is the run its usage is saved under.
        try:
            profile = await self._build_profile(user, config, build_id)
        finally:
            await self._llm_usage.record(
                user_id=user.id,
                run_id=build_id,
                operation=LLMOperation.TASTE_BUILD,
                usages=self._profiler.take_usages(),
                profile_name=config.name,
            )
            await self._release_lease(user, config, build_id)

        return profile

    async def _build_profile(
        self,
        user: User,
        config: BuildTasteProfileConfigInput,
        build_id: uuid.UUID,
    ) -> TasteProfile:
        # Cut the listening history into periods holding the same number of plays, each seeded with the tracks most
        # played in it: a period is described by what was listened to then, a track replayed years later in each.
        min_score = 0 if config.rated_only else None

        async with self._uow as uow:
            played_tracks = await uow.track_plays.count_played_tracks(user_id=user.id, min_score=min_score)

            seeds = min(config.track_limit, played_tracks)
            if not seeds:
                raise TasteProfileNoSeedError(f"No played tracks found for user {user.id}")

            tracks_per_period = config.batch_size or max(
                TASTE_BATCH_SIZE_MIN, math.ceil(seeds / TASTE_BATCH_COUNT_TARGET)
            )

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
                logger.debug(f"Resuming taste profile from period {start_batch_index + 1} / {len(periods)}")
            else:
                logger.warning("No checkpoint found for this profile, starting from scratch")

        await self._progress.publish(StepStarted(step=ProgressStep.TASTE_PERIODS, total=len(periods)))

        if start_batch_index:
            await self._progress.publish(
                StepResumed(step=ProgressStep.TASTE_PERIODS, done=start_batch_index, total=len(periods))
            )

        # Index of the step in progress; len(periods) denotes the final reflection step.
        step = start_batch_index + 1
        try:
            for i, period in enumerate(periods, start=1):
                if i <= start_batch_index:
                    continue

                step = i
                logger.debug(
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

                # One block per batch: a paid batch survives a later failure, and commits with its cost. Accepted risk:
                # the block rolled back (the lease taken over, the database unreachable) loses the cost of the period;
                # one period at most.
                usages = self._profiler.take_usages()

                async with self._uow as uow:
                    await self._renew_lease(uow, user, config, build_id)
                    await uow.taste_profiles.upsert_checkpoint(
                        user_id=user.id,
                        name=config.name,
                        title=config.title,
                        logic_version=self._profiler.logic_version,
                        profiler_metadata=self._profiler.profiler_metadata,
                        tracks_count=tracks_count,
                        profile_data=current_profile,
                        batch_index=i,
                    )
                    await self._llm_usage.add(
                        user.id, build_id, LLMOperation.TASTE_BUILD, usages, profile_name=config.name, uow=uow
                    )

                await self._progress.publish(StepAdvanced(step=ProgressStep.TASTE_PERIODS, done=i, total=len(periods)))

                if config.throttling_sleep_seconds > 0 and i < len(periods):
                    logger.debug(f"Throttling: sleeping {config.throttling_sleep_seconds}s before next batch")
                    await asyncio.sleep(config.throttling_sleep_seconds)

            await self._progress.publish(StepDone(step=ProgressStep.TASTE_PERIODS))

            # The merged profile is already checkpointed: a reflection failure is resumable too.
            step = len(periods)
            logger.debug("Processing psychographic reflection")
            await self._progress.publish(StepStarted(step=ProgressStep.TASTE_REFLECT))
            current_profile = await self._profiler.reflect_on_profile(cast(TasteProfileData, current_profile))
            await self._progress.publish(StepDone(step=ProgressStep.TASTE_REFLECT))
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
            title=config.title,
            profile=current_profile,
            profiler_metadata=self._profiler.profiler_metadata,
            tracks_count=tracks_count,
            logic_version=self._profiler.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ).sort_timeline()

        # The reflection's cost commits with the profile, as a period's with its checkpoint.
        usages = self._profiler.take_usages()

        async with self._uow as uow:
            await self._renew_lease(uow, user, config, build_id)
            taste_profile = await uow.taste_profiles.upsert(taste_profile)
            await self._llm_usage.add(
                user.id, build_id, LLMOperation.TASTE_BUILD, usages, profile_name=config.name, uow=uow
            )

        return taste_profile

    async def _renew_lease(
        self,
        uow: UnitOfWorkPort,
        user: User,
        config: BuildTasteProfileConfigInput,
        build_id: uuid.UUID,
    ) -> None:
        """Checks the fencing token in the block of a write, before it: a build whose lease was taken over stops."""
        renewed = await uow.taste_builds.renew(
            user_id=user.id,
            name=config.name,
            build_id=build_id,
            lease_duration=config.lease_duration,
        )
        if not renewed:
            raise TasteProfileBuildInProgressError(
                f"Another build took taste profile '{config.name}' over, its lease having expired: this one stopped"
            )

    async def _release_lease(self, user: User, config: BuildTasteProfileConfigInput, build_id: uuid.UUID) -> None:
        # A failure must not hide the outcome of the build: the lease then expires on its own.
        try:
            async with self._uow as uow:
                await uow.taste_builds.release(user_id=user.id, name=config.name, build_id=build_id)
        except Exception:
            logger.warning(
                f"Failed to release the lease of taste profile '{config.name}', it expires on its own",
                exc_info=True,
                extra={"user_id": str(user.id)},
            )
