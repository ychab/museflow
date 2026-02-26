from datetime import UTC
from datetime import datetime

import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken


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
