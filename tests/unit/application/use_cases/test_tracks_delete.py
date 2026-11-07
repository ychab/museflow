import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_delete import DeleteTracksUseCase
from museflow.domain.enums import MusicProvider

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
