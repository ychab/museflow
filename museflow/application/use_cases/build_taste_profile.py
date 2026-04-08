import asyncio
import itertools
import logging
import random
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
from museflow.domain.exceptions import TasteProfileNoSeedException
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
        total = await self._track_repository.count(user_id=user.id)
        offset = random.randint(0, max(0, total - config.track_limit))
        logger.debug(f"Taste profile seed: total={total}, limit={config.track_limit}, offset={offset}")

        tracks = await self._track_repository.get_list(
            user_id=user.id,
            order=[(TrackOrderBy.PLAYED_AT, SortOrder.ASC), (TrackOrderBy.ADDED_AT, SortOrder.ASC)],
            offset=offset,
            limit=config.track_limit,
        )
        if not tracks:
            raise TasteProfileNoSeedException(f"No tracks found for user {user.id}")

        # First iteration: no previous profile to merge with — seed the accumulator.
        # Subsequent iterations: merge the new segment into the running profile.
        current_profile: TasteProfileData | None = None
        batches = list(itertools.batched(tracks, config.batch_size, strict=False))
        for i, batch in enumerate(batches, start=1):
            logger.info(
                f"About processing taste profile batch {i} ({min(i * config.batch_size, len(tracks))} / {len(tracks)} tracks)"
            )
            segment = await self._profiler.build_profile_segment(list(batch))
            current_profile = (
                segment if current_profile is None else await self._profiler.merge_profiles(current_profile, segment)
            )
            if config.batch_sleep_seconds > 0 and i < len(batches):
                logger.debug(f"Throttling: sleeping {config.batch_sleep_seconds}s before next batch")
                await asyncio.sleep(config.batch_sleep_seconds)
        current_profile = cast(TasteProfileData, current_profile)  # Non-None guaranteed

        logger.info("About processing psychographic reflection")
        current_profile = await self._profiler.reflect_on_profile(current_profile)

        return await self._taste_profile_repository.upsert(
            TasteProfile(
                user_id=user.id,
                profiler=self._profiler.profiler_type,
                name=config.name,
                profile=current_profile,
                profiler_metadata=self._profiler.profiler_metadata,
                tracks_count=len(tracks),
                logic_version=self._profiler.logic_version,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
