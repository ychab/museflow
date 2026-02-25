import uuid

import pytest

from museflow.domain.ports.security import AccessTokenManagerPort
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.ports.security import StateTokenGeneratorPort


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


class TestSystemStateTokenGenerator:
    @pytest.mark.parametrize("length", [30, 50])
    def test__generate__nominal(self, state_token_generator: StateTokenGeneratorPort, length: int) -> None:
        token = state_token_generator.generate(length=length)
        assert len(token) == length
