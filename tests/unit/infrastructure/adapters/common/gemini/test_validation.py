import logging
from typing import Any
from unittest.mock import AsyncMock

from pydantic import BaseModel

import pytest

from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiFailureKind
from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiResponseError
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.validation import validate_response

VALID_RESPONSE: dict[str, Any] = {
    "candidates": [{"content": {"parts": [{"text": '{"value": 42}'}], "role": "model"}, "finishReason": "STOP"}]
}
INVALID_JSON_RESPONSE: dict[str, Any] = {
    "candidates": [{"content": {"parts": [{"text": '{"value": 4'}], "role": "model"}, "finishReason": "STOP"}]
}
SCHEMA_VIOLATION_RESPONSE: dict[str, Any] = {
    "candidates": [{"content": {"parts": [{"text": '{"value": "nope"}'}], "role": "model"}, "finishReason": "STOP"}]
}


class Answer(BaseModel):
    value: int


class Backend:
    def __init__(self, api: AsyncMock) -> None:
        self.api = api

    @validate_response(Answer, adapter="test")
    async def request(self, contents: list[GeminiRequestContent], flag: str, *, suffix: str = "") -> dict[str, Any]:
        return await self.api(contents, flag, suffix=suffix)  # type: ignore[no-any-return]


@pytest.fixture
def contents() -> list[GeminiRequestContent]:
    return [GeminiRequestContent(parts=[GeminiRequestPart(text="prompt")])]


@pytest.fixture
def api(request: pytest.FixtureRequest) -> AsyncMock:
    return AsyncMock(return_value=request.param)


class TestValidateResponse:
    @pytest.mark.parametrize("api", [VALID_RESPONSE], indirect=True)
    async def test__valid_reply__returns_model_and_forwards_arguments(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING):
            result = await Backend(api).request(contents, "flag", suffix="suffix")

        assert result == Answer(value=42)
        api.assert_awaited_once_with(contents, "flag", suffix="suffix")
        assert caplog.records == []

    @pytest.mark.parametrize(
        ("api", "expected_kind", "expected_finish_reason"),
        [
            pytest.param({"candidates": []}, GeminiFailureKind.NO_CANDIDATES, None, id="no_candidates"),
            pytest.param({}, GeminiFailureKind.NO_CANDIDATES, None, id="no_candidates_key"),
            pytest.param(
                {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                GeminiFailureKind.TRUNCATED,
                "MAX_TOKENS",
                id="truncated",
            ),
            pytest.param(
                {"candidates": [{"finishReason": "SAFETY"}]},
                GeminiFailureKind.EMPTY_RESPONSE,
                "SAFETY",
                id="no_content",
            ),
            pytest.param(
                {"candidates": [{"content": {"role": "model"}}]},
                GeminiFailureKind.EMPTY_RESPONSE,
                None,
                id="no_parts",
            ),
            pytest.param(
                {"candidates": [{"content": {"parts": [{"text": ""}], "role": "model"}}]},
                GeminiFailureKind.EMPTY_RESPONSE,
                None,
                id="empty_text",
            ),
        ],
        indirect=["api"],
    )
    async def test__unusable_reply__raises_non_self_healable_error(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        expected_kind: GeminiFailureKind,
        expected_finish_reason: str | None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING), pytest.raises(GeminiResponseError) as exc_info:
            await Backend(api).request(contents, "flag")

        assert exc_info.value.adapter == "test"
        assert exc_info.value.failure_kind == expected_kind
        assert exc_info.value.finish_reason == expected_finish_reason
        assert not exc_info.value.self_healable
        (record,) = caplog.records
        assert record.levelno == logging.WARNING
        assert record.__dict__["adapter"] == "test"
        assert record.__dict__["failure_kind"] == expected_kind.value
        assert record.__dict__["finish_reason"] == expected_finish_reason

    @pytest.mark.parametrize(
        ("api", "expected_kind", "expected_raw", "expected_detail"),
        [
            pytest.param(
                INVALID_JSON_RESPONSE,
                GeminiFailureKind.INVALID_JSON,
                '{"value": 4',
                "Expecting",
                id="invalid_json",
            ),
            pytest.param(
                SCHEMA_VIOLATION_RESPONSE,
                GeminiFailureKind.SCHEMA_VIOLATION,
                '{"value": "nope"}',
                "value:",
                id="schema_violation",
            ),
        ],
        indirect=["api"],
    )
    async def test__invalid_reply__raises_self_healable_error_with_raw_text(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        expected_kind: GeminiFailureKind,
        expected_raw: str,
        expected_detail: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING), pytest.raises(GeminiResponseError) as exc_info:
            await Backend(api).request(contents, "flag")

        assert exc_info.value.failure_kind == expected_kind
        assert exc_info.value.finish_reason == "STOP"
        assert exc_info.value.raw_text == expected_raw
        assert expected_detail in exc_info.value.detail
        assert exc_info.value.self_healable
        assert caplog.records[0].__dict__["raw_preview"] == expected_raw

    def test__decorated_method__keeps_its_name(self) -> None:
        assert Backend.request.__name__ == "request"
