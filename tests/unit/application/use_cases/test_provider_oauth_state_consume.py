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
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserNotFound


class TestConsumeOAuthState:
    async def test__state__unknown(
        self,
        mock_uow: mock.AsyncMock,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = None

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(state="dummy-state", provider=MusicProvider.SPOTIFY, uow=mock_uow)

    async def test__state__expired(
        self,
        mock_uow: mock.AsyncMock,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        expired_at = datetime.now(UTC) - timedelta(seconds=OAUTH_STATE_TTL_SECONDS)
        mock_auth_state_repository.consume.return_value = replace(auth_state, updated_at=expired_at)

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(state=auth_state.state, provider=auth_state.provider, uow=mock_uow)

    async def test__state__other_provider(
        self,
        mock_uow: mock.AsyncMock,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = auth_state

        with pytest.raises(ProviderOAuthStateInvalidError):
            await consume_oauth_state(
                state=auth_state.state,
                provider="FOO",  # type: ignore[arg-type]
                uow=mock_uow,
            )

    @pytest.mark.parametrize("auth_state", [{"user_id": uuid.uuid4()}], indirect=True)
    async def test__user__unknown(
        self,
        mock_uow: mock.AsyncMock,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = auth_state
        mock_user_repository.get_by_id.return_value = None

        with pytest.raises(UserNotFound):
            await consume_oauth_state(state=auth_state.state, provider=auth_state.provider, uow=mock_uow)
