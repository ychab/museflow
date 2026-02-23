from datetime import UTC
from datetime import datetime

import pytest

from spotifagent.domain.entities.auth import OAuthProviderTokenState


class TestOAuthProviderTokenState:
    @pytest.mark.parametrize(
        ("token_state", "expected_bool"),
        [
            ({"expires_at": datetime(2026, 1, 1, 0, 1, 10, tzinfo=UTC)}, False),
            ({"expires_at": datetime(2026, 1, 1, 0, 0, 50, tzinfo=UTC)}, True),
        ],
        indirect=["token_state"],
    )
    def test__is_expired(
        self, frozen_time: datetime, token_state: OAuthProviderTokenState, expected_bool: bool
    ) -> None:
        assert token_state.is_expired(60) is expected_bool
