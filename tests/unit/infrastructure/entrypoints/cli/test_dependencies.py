import pytest

from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profiler


class TestDependencies:
    async def test__get_advisor_adapter__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown advisor: FOO"):
            async with get_advisor_adapter(advisor="FOO"):  # type: ignore[arg-type]
                pass

    async def test__get_taste_profiler__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown profiler: FOO"):
            async with get_taste_profiler(profiler="FOO"):  # type: ignore[arg-type]
                pass
