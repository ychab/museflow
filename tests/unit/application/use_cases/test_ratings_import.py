from unittest import mock

from museflow.application.inputs.rate import RatingEntryInput
from museflow.application.use_cases.ratings_import import import_ratings
from museflow.domain.entities.user import User

from tests.unit.factories.entities.track import TrackFactory


class TestImportRatingsUseCase:
    async def test__fingerprint_not_found(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await import_ratings(
            user_id=user.id,
            entries=[RatingEntryInput(fingerprint="unknown-fp", score=5)],
            uow=mock_uow,
        )

        assert result.imported_count == 0
        assert result.not_found_count == 1
        mock_track_repository.rate.assert_not_awaited()

    async def test__score_skipped_entry__calls_skip(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(user_id=user.id, fingerprint="test-fingerprint-abc", score_skipped=False)
        mock_track_repository.get_list.return_value = [track]

        result = await import_ratings(
            user_id=user.id,
            entries=[RatingEntryInput(fingerprint=track.fingerprint, score_skipped=True)],
            uow=mock_uow,
        )

        mock_track_repository.skip.assert_awaited_once_with(user_id=user.id, track_id=track.id)
        mock_track_repository.rate.assert_not_awaited()
        assert result.skipped_count == 1
        assert result.imported_count == 0

    async def test__entry_with_no_score_and_not_skipped__is_ignored(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(user_id=user.id, fingerprint="test-fingerprint-noop", score_skipped=False)
        mock_track_repository.get_list.return_value = [track]

        result = await import_ratings(
            user_id=user.id,
            entries=[RatingEntryInput(fingerprint=track.fingerprint)],
            uow=mock_uow,
        )

        mock_track_repository.skip.assert_not_awaited()
        mock_track_repository.rate.assert_not_awaited()
        assert result.skipped_count == 0
        assert result.imported_count == 0
        assert result.not_found_count == 0
