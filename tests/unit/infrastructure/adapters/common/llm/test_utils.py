import httpx

import pytest

from museflow.infrastructure.adapters.common.llm.utils import parse_retry_after


class TestParseRetryAfter:
    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            pytest.param({"Retry-After": "38"}, 38, id="seconds"),
            pytest.param({"Retry-After": "38.9"}, 38, id="decimal_seconds"),
            pytest.param({"Retry-After": "-5"}, 0, id="negative"),
            pytest.param({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None, id="http_date"),
            pytest.param({}, None, id="missing"),
        ],
    )
    def test__parse(self, headers: dict[str, str], expected: int | None) -> None:
        assert parse_retry_after(httpx.Response(429, headers=headers)) == expected
