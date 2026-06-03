from unittest import mock

from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.discover.rate import rate_logic

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory
from tests.integration.factories.models.discovery import DiscoveryPlaylistTrackModelFactory


class TestRateLogic:
    async def test__nominal(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        track_db = await DiscoveryPlaylistTrackModelFactory.create_async(
            playlist_id=pl_db.id,
            position=0,
        )

        # Score 8 (above threshold), no blacklist prompts expected
        with mock.patch(
            "museflow.infrastructure.entrypoints.cli.commands.discover.rate.typer.prompt",
            return_value="8",
        ):
            await rate_logic(email=user.email, playlist_id=pl_db.id)

        result = await discovery_playlist_repository.get(user.id, pl_db.id)
        assert result is not None
        rated_track = next((t for t in result.tracks if t.id == track_db.id), None)
        assert rated_track is not None
        assert rated_track.score == 8
