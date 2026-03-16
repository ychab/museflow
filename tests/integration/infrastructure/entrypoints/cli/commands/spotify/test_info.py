import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.spotify.info import info_logic

from tests.integration.factories.models.music import TrackModelFactory


class TestSpotifyInfoLogic:
    async def test__user__not_found(self) -> None:
        with pytest.raises(UserNotFound):
            await info_logic(email="ghost@example.com")

    async def test__genres__nominal(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["electronic", "ambient"])
        await TrackModelFactory.create_async(user_id=user.id, genres=["electronic"])

        info_data = await info_logic(email=user.email, show_genres=True, show_token=False)

        assert "electronic" in info_data.genres
        assert "ambient" in info_data.genres

    async def test__genres__none(self, user: User) -> None:
        info_data = await info_logic(email=user.email, show_genres=True, show_token=False)
        assert info_data.genres == []

    async def test__token__nominal(self, user: User, auth_token: OAuthProviderUserToken) -> None:
        info_data = await info_logic(email=user.email, show_genres=False, show_token=True)

        assert info_data.token is not None
        assert info_data.token.token_access == auth_token.token_access
        assert info_data.token.token_refresh == auth_token.token_refresh

    async def test__token__none(self, user: User) -> None:
        info_data = await info_logic(email=user.email, show_genres=False, show_token=True)
        assert info_data.token is None

    async def test__all__nominal(self, user: User, auth_token: OAuthProviderUserToken) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["jazz"])

        info_data = await info_logic(email=user.email, show_genres=True, show_token=True)

        assert "jazz" in info_data.genres
        assert info_data.token is not None
        assert info_data.token.token_access == auth_token.token_access
        assert info_data.token.token_refresh == auth_token.token_refresh

    async def test__all__none(self, user: User) -> None:
        info_data = await info_logic(email=user.email, show_genres=True, show_token=True)

        assert info_data.genres == []
        assert info_data.token is None
