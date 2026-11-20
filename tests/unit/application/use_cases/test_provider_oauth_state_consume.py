import uuid
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest import mock

import pytest

from museflow.application.use_cases.provider_oauth_state_consume import consume_oauth_state
from museflow.domain.const import OAUTH_STATE_TTL_SECONDS
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderOAuthStateInvalidError


class TestConsumeOAuthStateUseCase:
    async def test__state__unknown(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = None

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(state="dummy-state", user=user, provider=MusicProvider.SPOTIFY, uow=mock_uow)

    async def test__state__expired(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        expired_at = datetime.now(UTC) - timedelta(seconds=OAUTH_STATE_TTL_SECONDS)
        mock_auth_state_repository.consume.return_value = replace(auth_state, updated_at=expired_at)

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(state=auth_state.state, user=user, provider=auth_state.provider, uow=mock_uow)

    async def test__state__other_provider(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = auth_state

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(
                state=auth_state.state,
                user=user,
                provider="FOO",  # type: ignore[arg-type]
                uow=mock_uow,
            )

    @pytest.mark.parametrize("auth_state", [{"user_id": uuid.uuid4()}], indirect=True)
    async def test__state__other_user(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        # #101: a state issued to someone else, whose code was sent to this user to finish the flow.
        mock_auth_state_repository.consume.return_value = auth_state

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(state=auth_state.state, user=user, provider=auth_state.provider, uow=mock_uow)
