from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from museflow.domain.const import OAUTH_STATE_TTL_SECONDS
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken


class TestOAuthProviderState:
    @pytest.mark.parametrize(
        ("auth_state", "expected_bool"),
        [
            ({"updated_at": datetime(2026, 1, 1, tzinfo=UTC) - timedelta(seconds=OAUTH_STATE_TTL_SECONDS - 1)}, False),
            ({"updated_at": datetime(2026, 1, 1, tzinfo=UTC) - timedelta(seconds=OAUTH_STATE_TTL_SECONDS)}, True),
        ],
        indirect=["auth_state"],
    )
    def test__is_expired(
        self,
        frozen_time: datetime,
        auth_state: OAuthProviderState,
        expected_bool: bool,
    ) -> None:
        assert auth_state.is_expired() is expected_bool


class TestOAuthProviderUserToken:
    @pytest.mark.parametrize(
        ("auth_token", "expected_bool"),
        [
            ({"token_expires_at": datetime(2026, 1, 1, 0, 1, 10, tzinfo=UTC)}, False),
            ({"token_expires_at": datetime(2026, 1, 1, 0, 0, 50, tzinfo=UTC)}, True),
        ],
        indirect=["auth_token"],
    )
    def test__is_expired(
        self,
        frozen_time: datetime,
        auth_token: OAuthProviderUserToken,
        expected_bool: bool,
    ) -> None:
        assert auth_token.is_expired(60) is expected_bool
