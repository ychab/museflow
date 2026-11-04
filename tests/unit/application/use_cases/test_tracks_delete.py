import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_delete import TracksDeleteUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource

from tests.unit.factories.entities.track import TrackFactory


class TestTracksDeleteUseCase:
    @pytest.fixture
    def use_case(self, mock_uow: mock.AsyncMock) -> TracksDeleteUseCase:
        return TracksDeleteUseCase(uow=mock_uow)

    async def test__find__name_filter__case_insensitive(
        self,
        use_case: TracksDeleteUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        matching = TrackFactory.build(name="Creep")
        mock_track_repository.get_list.return_value = [matching, TrackFactory.build(name="Karma Police")]

        tracks = await use_case.find(user_id=uuid.uuid4(), artist=None, name="creep", source=None, provider=None)

        assert tracks == [matching]

    async def test__find__filters_passed_to_repository(
        self,
        use_case: TracksDeleteUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        mock_track_repository.get_list.return_value = []

        await use_case.find(
            user_id=user_id,
            artist="Radiohead",
            name=None,
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user_id,
            artist_name="Radiohead",
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )

    async def test__delete__no_provider__deletes_the_ids(
        self,
        use_case: TracksDeleteUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        track_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_track_repository.delete.return_value = 2

        deleted = await use_case.delete(user_id=user_id, track_ids=track_ids, provider=None)

        assert deleted == 2
        mock_track_repository.unlink_provider.assert_not_awaited()
        mock_track_repository.delete.assert_awaited_once_with(user_id=user_id, track_ids=track_ids)

    async def test__delete__provider__deletes_the_orphans_only(
        self,
        use_case: TracksDeleteUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        track_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_track_repository.unlink_provider.return_value = track_ids[:1]
        mock_track_repository.delete.return_value = 1

        deleted = await use_case.delete(user_id=user_id, track_ids=track_ids, provider=MusicProvider.SPOTIFY)

        assert deleted == 1
        mock_track_repository.unlink_provider.assert_awaited_once_with(
            user_id=user_id,
            provider=MusicProvider.SPOTIFY,
            track_ids=track_ids,
        )
        mock_track_repository.delete.assert_awaited_once_with(user_id=user_id, track_ids=track_ids[:1])
