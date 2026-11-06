import uuid
from collections.abc import Iterator
from unittest import mock

import pytest
from argon2 import PasswordHasher as Argon2Hasher

from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort


class TestArgon2PasswordHasher:
    @pytest.fixture
    def spy_argon2_verify(self) -> Iterator[mock.Mock]:
        with mock.patch.object(Argon2Hasher, "verify", autospec=True, side_effect=Argon2Hasher.verify) as spy:
            yield spy

    def test__verify__nominal(self, password_hasher: PasswordHasherPort) -> None:
        password = "testtest"
        hashed_password = password_hasher.hash(password)
        assert password_hasher.verify(password, hashed_password) is True

    def test__verify__wrong(self, password_hasher: PasswordHasherPort) -> None:
        hashed_password = password_hasher.hash("blahblah")
        assert password_hasher.verify("testtest", hashed_password) is False

    def test__verify_dummy__same_cost_as_verify(
        self,
        password_hasher: PasswordHasherPort,
        spy_argon2_verify: mock.Mock,
    ) -> None:
        password_hasher.verify_dummy("testtest")

        spy_argon2_verify.assert_called_once()
        _, dummy_hash, password = spy_argon2_verify.call_args.args
        assert password == "testtest"
        assert Argon2Hasher().check_needs_rehash(dummy_hash) is False


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
