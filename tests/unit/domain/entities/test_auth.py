from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.auth import OAuthProviderUserTokenUpdate


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


class TestOAuthProviderUserTokenUpdate:
    @pytest.mark.parametrize("data", [{"token_type": "bearer"}, {"token_type": None}])
    def test_validate_one_field_set__nominal(self, data: dict[str, Any]) -> None:
        auth_token_data = OAuthProviderUserTokenUpdate(**data)
        assert auth_token_data is not None

    def test_validate_one_field_set__error(self) -> None:
        with pytest.raises(ValueError, match="At least one field must be provided for update"):
            OAuthProviderUserTokenUpdate()
