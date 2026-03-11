import pytest

from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_client


class TestDependencies:
    async def test__get_advisor_client__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown advisor: FOO"):
            async with get_advisor_client(advisor="FOO"):  # type: ignore[arg-type]
                pass
