from unittest import mock

import pytest

from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_agent_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_similar_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profiler


class TestDependencies:
    async def test__get_advisor_similar_adapter__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown advisor: FOO"):
            async with get_advisor_similar_adapter(advisor="FOO"):  # type: ignore[arg-type]
                pass

    async def test__get_advisor_agent_adapter__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown advisor agent: FOO"):
            async with get_advisor_agent_adapter(advisor_agent="FOO"):  # type: ignore[arg-type]
                pass

    async def test__get_taste_profiler__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown profiler: FOO"):
            async with get_taste_profiler(profiler="FOO"):  # type: ignore[arg-type]
                pass

    async def test__get_provider_oauth__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with get_provider_oauth(provider="FOO"):  # type: ignore[arg-type]
                pass

    def test__get_provider_library_factory__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            get_provider_library_factory(provider="FOO", session=mock.Mock(), oauth_client=mock.Mock())  # type: ignore[arg-type]
