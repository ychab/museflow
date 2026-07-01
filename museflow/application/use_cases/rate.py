import uuid

from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.exceptions import RateScoreInvalidException


async def track_rate(
    track_id: uuid.UUID,
    score: int,
    user_id: uuid.UUID,
    track_repository: TrackRepository,
) -> None:
    if not DISCOVERY_TRACK_SCORE_MIN <= score <= DISCOVERY_TRACK_SCORE_MAX:
        raise RateScoreInvalidException(
            f"Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, got {score}"
        )
    await track_repository.rate(user_id=user_id, track_id=track_id, score=score)


async def track_skip(
    track_id: uuid.UUID,
    user_id: uuid.UUID,
    track_repository: TrackRepository,
) -> None:
    await track_repository.skip(user_id=user_id, track_id=track_id)
