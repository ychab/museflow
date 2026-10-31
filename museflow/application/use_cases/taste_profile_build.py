import asyncio
import itertools
import logging
from datetime import UTC
from datetime import datetime
from typing import cast

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.user import User
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.exceptions import TasteProfileBuildPausedException
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import TasteProfilerRateLimitExceeded

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
        # Select the most-listened tracks as seeds (best signal quality)
        async with self._uow as uow:
            tracks = await uow.tracks.get_list(
                user_id=user.id,
                min_score=0 if config.rated_only else None,
                order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
                limit=config.track_limit,
            )
        if not tracks:
            raise TasteProfileNoSeedException(f"No tracks found for user {user.id}")

        # Re-sort chronologically so the LLM builds coherent taste eras from date-range batches.
        max_dt = datetime.max.replace(tzinfo=UTC)
        tracks = sorted(tracks, key=lambda t: t.played_at_last or max_dt)
        logger.debug(f"Taste profile seeds: {len(tracks)} tracks (most played, chronological order)")

        batches = list(itertools.batched(tracks, config.batch_size, strict=False))

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
                    f"About processing taste profile batch {i} ({min(i * config.batch_size, len(tracks))} / {len(tracks)} tracks)"
                )

                segment = await self._profiler.build_profile_segment(list(batch))
                current_profile = (
                    segment
                    if current_profile is None
                    else await self._profiler.merge_profiles(current_profile, segment)
                )

                # One block per batch: a paid batch survives a later failure.
                async with self._uow as uow:
                    await uow.taste_profiles.save_checkpoint(
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
            logger.info("About processing psychographic reflection")
            current_profile = await self._profiler.reflect_on_profile(cast(TasteProfileData, current_profile))
        except (TasteProfilerRateLimitExceeded, TasteProfileBuildException) as e:
            logger.warning(f"Taste profile build failed at step {step} / {len(batches)}, pausing build: {e}")
            raise TasteProfileBuildPausedException(step, len(batches), reason=str(e)) from e

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
