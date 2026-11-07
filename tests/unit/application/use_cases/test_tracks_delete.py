import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_delete import DeleteTracksUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource

from tests.unit.factories.entities.track import TrackFactory


class TestDeleteTracksUseCase:
    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def provider(self, request: pytest.FixtureRequest) -> MusicProvider | None:
        return getattr(request, "param", None)

    @pytest.fixture
    def use_case(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None,
        mock_uow: mock.AsyncMock,
    ) -> DeleteTracksUseCase:
        return DeleteTracksUseCase(user_id=user_id, provider=provider, uow=mock_uow)

    async def test__find__name_filter__case_insensitive(
        self,
        use_case: DeleteTracksUseCase,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        matching = TrackFactory.build(name="Creep")
        mock_track_repository.get_list.return_value = [matching, TrackFactory.build(name="Karma Police")]

        tracks = await use_case.find(artist=None, name="creep", source=None)

        assert tracks == [matching]

    @pytest.mark.parametrize("provider", [MusicProvider.SPOTIFY], indirect=True)
    async def test__find__filters_passed_to_repository(
        self,
        use_case: DeleteTracksUseCase,
        user_id: uuid.UUID,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await use_case.find(artist="Radiohead", name=None, source=TrackSource.HISTORY)

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user_id,
            artist_name="Radiohead",
            source=TrackSource.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )

    async def test__delete__no_provider__deletes_the_ids(
        self,
        use_case: DeleteTracksUseCase,
        user_id: uuid.UUID,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_track_repository.delete.return_value = 2

        deleted = await use_case.delete(track_ids=track_ids)

        assert deleted == 2
        mock_track_repository.unlink_provider.assert_not_awaited()
        mock_track_repository.delete.assert_awaited_once_with(user_id=user_id, track_ids=track_ids)

    @pytest.mark.parametrize("provider", [MusicProvider.SPOTIFY], indirect=True)
    async def test__delete__provider__deletes_the_orphans_only(
        self,
        use_case: DeleteTracksUseCase,
        user_id: uuid.UUID,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_track_repository.unlink_provider.return_value = track_ids[:1]
        mock_track_repository.delete.return_value = 1

        deleted = await use_case.delete(track_ids=track_ids)

        assert deleted == 1
        mock_track_repository.unlink_provider.assert_awaited_once_with(
            user_id=user_id,
            provider=MusicProvider.SPOTIFY,
            track_ids=track_ids,
        )
        mock_track_repository.delete.assert_awaited_once_with(user_id=user_id, track_ids=track_ids[:1])

    async def test__delete_all__no_provider__deletes_every_track(
        self,
        use_case: DeleteTracksUseCase,
        user_id: uuid.UUID,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.delete_all.return_value = 3

        deleted = await use_case.delete_all()

        assert deleted == 3
        mock_track_repository.unlink_provider.assert_not_awaited()
        mock_track_repository.delete_all.assert_awaited_once_with(user_id=user_id)

    @pytest.mark.parametrize("provider", [MusicProvider.SPOTIFY], indirect=True)
    async def test__delete_all__provider__deletes_the_orphans_only(
        self,
        use_case: DeleteTracksUseCase,
        user_id: uuid.UUID,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        orphan_ids = [uuid.uuid4()]
        mock_track_repository.unlink_provider.return_value = orphan_ids
        mock_track_repository.delete.return_value = 1

        deleted = await use_case.delete_all()

        assert deleted == 1
        mock_track_repository.unlink_provider.assert_awaited_once_with(user_id=user_id, provider=MusicProvider.SPOTIFY)
        mock_track_repository.delete.assert_awaited_once_with(user_id=user_id, track_ids=orphan_ids)
        mock_track_repository.delete_all.assert_not_awaited()
