import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.rate import track_rate
from museflow.application.use_cases.rate import track_skip
from museflow.domain.exceptions import RateScoreInvalidException
from museflow.domain.exceptions import TrackNotFoundError


class TestTrackRateUseCase:
    async def test__nominal(self, mock_track_repository: mock.AsyncMock) -> None:
        track_id = uuid.uuid4()
        user_id = uuid.uuid4()
        score = 5

        await track_rate(track_id=track_id, score=score, user_id=user_id, track_repository=mock_track_repository)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user_id, track_id=track_id, score=score)

    async def test__raises_when_score_too_low(self, mock_track_repository: mock.AsyncMock) -> None:
        with pytest.raises(RateScoreInvalidException):
            await track_rate(
                track_id=uuid.uuid4(),
                score=-1,
                user_id=uuid.uuid4(),
                track_repository=mock_track_repository,
            )

        mock_track_repository.rate.assert_not_awaited()

    async def test__raises_when_score_too_high(self, mock_track_repository: mock.AsyncMock) -> None:
        with pytest.raises(RateScoreInvalidException):
            await track_rate(
                track_id=uuid.uuid4(),
                score=11,
                user_id=uuid.uuid4(),
                track_repository=mock_track_repository,
            )

        mock_track_repository.rate.assert_not_awaited()

    async def test__propagates_track_not_found(self, mock_track_repository: mock.AsyncMock) -> None:
        mock_track_repository.rate.side_effect = TrackNotFoundError()

        with pytest.raises(TrackNotFoundError):
            await track_rate(
                track_id=uuid.uuid4(),
                score=5,
                user_id=uuid.uuid4(),
                track_repository=mock_track_repository,
            )


class TestTrackSkipUseCase:
    async def test__nominal(self, mock_track_repository: mock.AsyncMock) -> None:
        track_id = uuid.uuid4()
        user_id = uuid.uuid4()

        await track_skip(track_id=track_id, user_id=user_id, track_repository=mock_track_repository)

        mock_track_repository.skip.assert_awaited_once_with(user_id=user_id, track_id=track_id)

    async def test__propagates_track_not_found(self, mock_track_repository: mock.AsyncMock) -> None:
        mock_track_repository.skip.side_effect = TrackNotFoundError()

        with pytest.raises(TrackNotFoundError):
            await track_skip(
                track_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                track_repository=mock_track_repository,
            )
