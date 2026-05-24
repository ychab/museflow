import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.spotify.info import info_logic


class TestSpotifyInfoLogic:
    async def test__user__not_found(self) -> None:
        with pytest.raises(UserNotFound):
            await info_logic(email="ghost@example.com")

    async def test__token__nominal(self, user: User, auth_token: OAuthProviderUserToken) -> None:
        token = await info_logic(email=user.email)

        assert token is not None
        assert token.token_access == auth_token.token_access
        assert token.token_refresh == auth_token.token_refresh

    async def test__token__none(self, user: User) -> None:
        token = await info_logic(email=user.email)
        assert token is None
