from typing import Final

from pydantic import SecretStr

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.security import AesSivTokenCipher
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.provider.reencrypt_tokens import provider_reencrypt_tokens_logic

FORMER_KEY: Final[SecretStr] = SecretStr("a-former-key-of-at-least-32-characters")


class TestProviderReencryptTokensLogic:
    @pytest.fixture(autouse=True)
    def fallback_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "PROVIDER_TOKEN_ENCRYPTION_KEY_FALLBACKS", [FORMER_KEY])

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token = await OAuthProviderTokenSQLRepository(async_session_db, AesSivTokenCipher(key=FORMER_KEY)).upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        reencrypted = await provider_reencrypt_tokens_logic()

        assert reencrypted == 1
        assert await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) == auth_token
