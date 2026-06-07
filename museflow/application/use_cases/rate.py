import uuid

from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.exceptions import RateScoreInvalidException
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN


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
