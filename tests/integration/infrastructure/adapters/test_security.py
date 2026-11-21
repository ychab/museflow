import uuid

import pytest

from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.security import TokenCipherPort
from museflow.domain.exceptions import TokenDecryptionError


class TestArgon2PasswordHasher:
    def test__verify__nominal(self, password_hasher: PasswordHasherPort) -> None:
        password = "testtest"
        hashed_password = password_hasher.hash(password)
        assert password_hasher.verify(password, hashed_password) is True

    def test__verify__wrong(self, password_hasher: PasswordHasherPort) -> None:
        hashed_password = password_hasher.hash("blahblah")
        assert password_hasher.verify("testtest", hashed_password) is False


class TestJwtAccessTokenManager:
    @pytest.mark.parametrize("user_id", [uuid.uuid4()])
    def test__decode__nominal(self, access_token_manager: AccessTokenManagerPort, user_id: uuid.UUID) -> None:
        token = access_token_manager.create({"sub": str(user_id)})

        payload = access_token_manager.decode(token)
        assert payload["sub"] == str(user_id)


class TestAesSivTokenCipher:
    def test__encrypt__deterministic(self, token_cipher: TokenCipherPort) -> None:
        # The compare-and-swap of the token refresh compares encrypted bytes: equal tokens must give equal bytes
        assert token_cipher.encrypt("token", context="row:column") == token_cipher.encrypt(
            "token", context="row:column"
        )

    def test__decrypt__other_context(self, token_cipher: TokenCipherPort) -> None:
        ciphertext = token_cipher.encrypt("token", context="row:column")

        with pytest.raises(TokenDecryptionError):
            token_cipher.decrypt(ciphertext, context="other-row:column")


class TestSystemStateTokenGenerator:
    @pytest.mark.parametrize("length", [30, 50])
    def test__generate__nominal(self, state_token_generator: StateTokenGeneratorPort, length: int) -> None:
        token = state_token_generator.generate(length=length)
        assert len(token) == length
