import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.track_rate import RateTrackUseCase
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import RateScoreInvalidException

from tests.unit.factories.entities.track import TrackFactory


class TestRateTrackUseCase:
    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def use_case(
        self,
        user_id: uuid.UUID,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> RateTrackUseCase:
        return RateTrackUseCase(
            user_id=user_id,
            provider=MusicProvider.SPOTIFY,
            uow=mock_uow,
            provider_library=mock_provider_library,
        )

    async def test__find_playlist__not_found(
        self,
        use_case: RateTrackUseCase,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await use_case.find_playlist(playlist_id=uuid.uuid4())

    async def test__play(self, use_case: RateTrackUseCase, mock_provider_library: mock.AsyncMock) -> None:
        track = TrackFactory.build(
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="spotify-id")]
        )

        await use_case.play(track)

        mock_provider_library.play_track.assert_awaited_once_with("spotify-id")

    async def test__play__track_not_linked(
        self,
        use_case: RateTrackUseCase,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        track = mock.MagicMock(spec=Track)
        track.get_provider_id.return_value = None

        await use_case.play(track)

        mock_provider_library.play_track.assert_not_awaited()

    async def test__play__no_active_device(
        self,
        use_case: RateTrackUseCase,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        mock_provider_library.play_track.side_effect = ProviderNoActiveDeviceException()

        with pytest.raises(ProviderNoActiveDeviceException):
            await use_case.play(TrackFactory.build())

    async def test__play__without_library(self, user_id: uuid.UUID, mock_uow: mock.AsyncMock) -> None:
        use_case = RateTrackUseCase(user_id=user_id, provider=None, uow=mock_uow)

        with pytest.raises(ValueError, match="Playback needs a provider"):
            await use_case.play(TrackFactory.build())

    @pytest.mark.parametrize("score", [-1, 11])
    async def test__rate__score_out_of_range(
        self,
        use_case: RateTrackUseCase,
        mock_track_repository: mock.AsyncMock,
        score: int,
    ) -> None:
        with pytest.raises(RateScoreInvalidException):
            await use_case.rate(track_id=uuid.uuid4(), score=score)

        mock_track_repository.rate.assert_not_awaited()
