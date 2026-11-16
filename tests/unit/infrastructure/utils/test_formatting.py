from datetime import timedelta

import pytest

from museflow.infrastructure.utils.formatting import format_duration


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(8.43, "8.4s"), (249, "4m09s"), (3725, "1h02m")],
    )
    def test__nominal(self, seconds: float, expected: str) -> None:
        assert format_duration(timedelta(seconds=seconds)) == expected
