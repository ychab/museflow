from typing import Any

import pytest

from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate


class TestOAuthProviderUserTokenUpdate:
    @pytest.mark.parametrize("data", [{"token_type": "bearer"}, {"token_type": None}])
    def test_validate_one_field_set__nominal(self, data: dict[str, Any]) -> None:
        auth_token_data = OAuthProviderUserTokenUpdate(**data)
        assert auth_token_data is not None

    def test_validate_one_field_set__error(self) -> None:
        with pytest.raises(ValueError, match="At least one field must be provided for update"):
            OAuthProviderUserTokenUpdate()
