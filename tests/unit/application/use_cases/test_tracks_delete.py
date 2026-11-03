import uuid
from unittest import mock

from museflow.application.use_cases.tracks_delete import delete_tracks
from museflow.application.use_cases.tracks_delete import find_tracks_to_delete
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource

from tests.unit.factories.entities.track import TrackFactory


class TestFindTracksToDeleteUseCase:
    async def test__name_filter__case_insensitive(
        self,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        matching = TrackFactory.build(name="Creep")
        mock_track_repository.get_list.return_value = [matching, TrackFactory.build(name="Karma Police")]

        tracks = await find_tracks_to_delete(
            user_id=uuid.uuid4(),
            artist=None,
            name="creep",
            source=None,
            provider=None,
            uow=mock_uow,
        )

        assert tracks == [matching]

    async def test__filters_passed_to_repository(
        self,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        mock_track_repository.get_list.return_value = []

        await find_tracks_to_delete(
            user_id=user_id,
            artist="Radiohead",
            name=None,
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
            uow=mock_uow,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user_id,
            artist_name="Radiohead",
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )


class TestDeleteTracksUseCase:
    async def test__filters_passed_to_repository(
        self,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user_id = uuid.uuid4()
        mock_track_repository.delete.return_value = 1

        deleted = await delete_tracks(
            user_id=user_id,
            artist="Radiohead",
            name="Creep",
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
            uow=mock_uow,
        )

        assert deleted == 1
        mock_track_repository.delete.assert_awaited_once_with(
            user_id=user_id,
            artist_name="Radiohead",
            track_name="Creep",
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )
