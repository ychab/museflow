import asyncio
from collections.abc import Callable
from collections.abc import Iterable
from unittest import mock

from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.domain.entities.auth import OAuthProviderUserTokenCreate
from museflow.domain.entities.music import MusicProvider
from museflow.domain.entities.users import User
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel
from museflow.infrastructure.entrypoints.cli.commands.spotify import connect_logic


class TestSpotifyConnectLogic:
    @pytest.fixture(autouse=True)
    def mock_typer_launch(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.connect.typer.launch"
        with mock.patch(target_path) as patched:
            yield patched

    @pytest.fixture
    def simulate_oauth_callback(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreate,
        async_session_db: AsyncSession,
    ) -> Callable[[float], asyncio.Task]:
        """
        Helper to simulate the external OAuth callback in the background.
        Yeah, I had to confess for this one: thank Gemini pro!
        """

        def _trigger(delay: float = 0.2) -> asyncio.Task:
            async def _background_update():
                # Wait for the CLI to start polling
                await asyncio.sleep(delay)

                # Delete user auth state.
                stmt_delete = delete(AuthProviderStateModel).where(
                    AuthProviderStateModel.user_id == user.id,
                    AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
                )
                await async_session_db.execute(stmt_delete)

                # Then create a new account.
                stmt_insert = insert(AuthProviderTokenModel).values(
                    user_id=user.id,
                    provider=MusicProvider.SPOTIFY,
                    token_type=auth_token_create.token_type,
                    token_access=auth_token_create.token_access,
                    token_refresh=auth_token_create.token_refresh,
                    token_expires_at=auth_token_create.token_expires_at,
                )
                await async_session_db.execute(stmt_insert)

                # Flush to make this change visible to the CLI's query
                await async_session_db.flush()

            return asyncio.create_task(_background_update())

        return _trigger

    async def test__nominal(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreate,
        simulate_oauth_callback: Callable[[float], asyncio.Task],
        async_session_db: AsyncSession,
        capsys: pytest.CaptureFixture,
    ) -> None:
        # Start the "callback" simulator in the background
        task = simulate_oauth_callback(0.2)

        await connect_logic(user.email, timeout=2.0, poll_interval=0.1)
        # Ensure the background task completed without error
        await task

        stmt_state = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_state = await async_session_db.execute(stmt_state)
        auth_state_db = result_state.scalar_one_or_none()
        assert auth_state_db is None

        stmt_token = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result_token = await async_session_db.execute(stmt_token)
        auth_token_db = result_token.scalar_one_or_none()
        assert auth_token_db is not None
        assert auth_token_db.token_type == auth_token_create.token_type
        assert auth_token_db.token_access == auth_token_create.token_access
        assert auth_token_db.token_refresh == auth_token_create.token_refresh
        assert auth_token_db.token_expires_at == auth_token_create.token_expires_at
