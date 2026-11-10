from collections.abc import Iterator
from unittest import mock

import pytest
from argon2 import PasswordHasher as Argon2Hasher

from museflow.infrastructure.adapters.security import Argon2PasswordHasher


class TestArgon2PasswordHasher:
    @pytest.fixture
    def spy_argon2_verify(self) -> Iterator[mock.Mock]:
        with mock.patch.object(Argon2Hasher, "verify", autospec=True, side_effect=Argon2Hasher.verify) as spy:
            yield spy

    def test__verify_simulate__same_cost_as_verify(self, spy_argon2_verify: mock.Mock) -> None:
        Argon2PasswordHasher().verify_simulate("testtest")

        spy_argon2_verify.assert_called_once()
        _, dummy_hash, password = spy_argon2_verify.call_args.args
        assert password == "testtest"
        assert Argon2Hasher().check_needs_rehash(dummy_hash) is False
