from unittest import mock

import pytest

from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_streaming_history_adapter


class TestDependencies:
    async def test__get_provider_oauth__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with get_provider_oauth(provider="FOO"):  # type: ignore[arg-type]
                pass

    def test__get_provider_library_factory__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            get_provider_library_factory(provider="FOO", oauth_client=mock.Mock())  # type: ignore[arg-type]

    def test__get_streaming_history_adapter__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            get_streaming_history_adapter(provider="FOO")  # type: ignore[arg-type]
