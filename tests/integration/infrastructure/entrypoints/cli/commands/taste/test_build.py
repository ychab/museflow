from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.domain.entities.user import User
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.entrypoints.cli.commands.taste.build import build_logic

from tests.unit.factories.entities.taste import TasteProfileFactory


class TestTasteBuildLogic:
    """
    The purpose of this test is to check that the user is loaded correctly from DB.
    Otherwise, we trust use case integration tests and avoid duplication.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.build.BuildTasteProfileUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    async def test__nominal(
        self,
        user: User,
        mock_use_case: mock.Mock,
    ) -> None:
        expected_profile = TasteProfileFactory.build(user_id=user.id)
        mock_use_case.build_profile.return_value = expected_profile

        profile = await build_logic(email=user.email, profiler=TasteProfiler.GEMINI, track_limit=3000, batch_size=400)

        assert profile == expected_profile
