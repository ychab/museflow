import asyncio
import itertools
import logging
from datetime import UTC
from datetime import datetime
from typing import cast

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.user import User
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.exceptions import TasteProfileBuildPausedException
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import TasteProfilerRateLimitExceeded
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy

logger = logging.getLogger(__name__)


class BuildTasteProfileUseCase:
    def __init__(
        self,
        profiler: TasteProfilerPort,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        self._profiler = profiler
        self._track_repository = track_repository
        self._taste_profile_repository = taste_profile_repository

    async def build_profile(self, user: User, config: BuildTasteProfileConfigInput) -> TasteProfile:
        # Select the most-listened tracks as seeds (best signal quality)
        tracks = await self._track_repository.get_list(
            user_id=user.id,
            order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
            limit=config.track_limit,
        )
        if not tracks:
            raise TasteProfileNoSeedException(f"No tracks found for user {user.id}")

        # Re-sort chronologically so Gemini builds coherent taste eras from date-range batches.
        max_dt = datetime.max.replace(tzinfo=UTC)
        tracks = sorted(tracks, key=lambda t: t.played_at_last or max_dt)
        logger.debug(f"Taste profile seeds: {len(tracks)} tracks (most played, chronological order)")

        batches = list(itertools.batched(tracks, config.batch_size, strict=False))

        # Load checkpoint if resuming
        start_batch_index = 0
        current_profile: TasteProfileData | None = None
        if config.resume:
            checkpoint = await self._taste_profile_repository.get_checkpoint(user.id, config.name)
            if checkpoint is not None:
                current_profile, start_batch_index = checkpoint
                logger.info(f"Resuming taste profile from batch {start_batch_index + 1} / {len(batches)}")
            else:
                logger.warning("No checkpoint found for this profile, starting from scratch")

        for i, batch in enumerate(batches, start=1):
            if i <= start_batch_index:
                continue

            logger.info(
                f"About processing taste profile batch {i} ({min(i * config.batch_size, len(tracks))} / {len(tracks)} tracks)"
            )

            try:
                segment = await self._profiler.build_profile_segment(list(batch))
                current_profile = (
                    segment
                    if current_profile is None
                    else await self._profiler.merge_profiles(current_profile, segment)
                )
            except (TasteProfilerRateLimitExceeded, TasteProfileBuildException) as e:
                logger.warning(f"Taste profile batch {i} failed, pausing build: {e}")
                raise TasteProfileBuildPausedException(i, len(batches), reason=str(e)) from e

            await self._taste_profile_repository.save_checkpoint(
                user_id=user.id,
                name=config.name,
                profiler=self._profiler.profiler_type,
                logic_version=self._profiler.logic_version,
                profiler_metadata=self._profiler.profiler_metadata,
                tracks_count=len(tracks),
                profile_data=current_profile,
                batch_index=i,
            )

            if config.throttling_sleep_seconds > 0 and i < len(batches):
                logger.debug(f"Throttling: sleeping {config.throttling_sleep_seconds}s before next batch")
                await asyncio.sleep(config.throttling_sleep_seconds)

        logger.info("About processing psychographic reflection")
        current_profile = await self._profiler.reflect_on_profile(cast(TasteProfileData, current_profile))

        taste_profile = TasteProfile(
            user_id=user.id,
            profiler=self._profiler.profiler_type,
            name=config.name,
            profile=current_profile,
            profiler_metadata=self._profiler.profiler_metadata,
            tracks_count=len(tracks),
            logic_version=self._profiler.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ).sort_timeline()

        return await self._taste_profile_repository.upsert(taste_profile)
