from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import delete_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestDeleteLogic:
    async def test__nominal__by_artist(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        await TrackModelFactory.create_async(user_id=user.id, artists=["Portishead"])

        result = await delete_logic(
            email=user.email, artist="Radiohead", name=None, source=None, provider=None, yes=True
        )
        assert result.deleted_count == 1

        remaining = await delete_logic(
            email=user.email, artist="Portishead", name=None, source=None, provider=None, yes=True
        )
        assert remaining.deleted_count == 1
