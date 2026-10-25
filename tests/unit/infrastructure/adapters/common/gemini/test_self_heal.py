import logging
from typing import Any
from unittest.mock import AsyncMock

from pydantic import BaseModel

import pytest

from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiFailureKind
from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiResponseError
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.self_heal import self_heal
from museflow.infrastructure.adapters.common.gemini.validation import validate_response
from museflow.infrastructure.config.settings.gemini import gemini_settings

INVALID_ERROR = GeminiResponseError(
    "invalid",
    adapter="test",
    failure_kind=GeminiFailureKind.SCHEMA_VIOLATION,
    raw_text='{"value": "nope"}',
    detail="value: Input should be a valid integer",
)
TRUNCATED_ERROR = GeminiResponseError("truncated", adapter="test", failure_kind=GeminiFailureKind.TRUNCATED)

VALID_RESPONSE: dict[str, Any] = {
    "candidates": [{"content": {"parts": [{"text": '{"value": 42}'}], "role": "model"}, "finishReason": "STOP"}]
}
INVALID_RESPONSE: dict[str, Any] = {
    "candidates": [{"content": {"parts": [{"text": '{"value": "nope"}'}], "role": "model"}, "finishReason": "STOP"}]
}


class Answer(BaseModel):
    value: int


class Backend:
    def __init__(self, api: AsyncMock) -> None:
        self.api = api

    @self_heal()
    async def request(self, contents: list[GeminiRequestContent], flag: str, *, suffix: str = "") -> Answer:
        return await self.api(contents, flag, suffix=suffix)  # type: ignore[no-any-return]

    @self_heal(max_retries=0)
    async def request_without_retry(self, contents: list[GeminiRequestContent]) -> Answer:
        return await self.api(contents)  # type: ignore[no-any-return]

    @self_heal()
    @validate_response(Answer, adapter="test")
    async def request_validated(self, contents: list[GeminiRequestContent]) -> dict[str, Any]:
        return await self.api(contents)  # type: ignore[no-any-return]


@pytest.fixture
def contents() -> list[GeminiRequestContent]:
    return [GeminiRequestContent(parts=[GeminiRequestPart(text="prompt")])]


@pytest.fixture
def api(request: pytest.FixtureRequest) -> AsyncMock:
    return AsyncMock(side_effect=request.param)


class TestSelfHeal:
    @pytest.mark.parametrize("api", [[Answer(value=42)]], indirect=True)
    async def test__valid_first_attempt__returns_result_and_forwards_arguments(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            result = await Backend(api).request(contents, "flag", suffix="suffix")

        assert result == Answer(value=42)
        api.assert_awaited_once_with(contents, "flag", suffix="suffix")
        assert caplog.records == []

    @pytest.mark.parametrize("api", [[INVALID_ERROR, Answer(value=42)]], indirect=True)
    async def test__invalid_then_valid__retries_with_feedback_and_logs_recovery(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            result = await Backend(api).request(contents, "flag", suffix="suffix")

        assert result == Answer(value=42)
        first_call, second_call = api.await_args_list
        assert first_call.args[0] == contents
        retried_conversation: list[GeminiRequestContent] = second_call.args[0]
        assert [content.role for content in retried_conversation] == [None, "model", "user"]
        assert retried_conversation[1].parts[0].text == INVALID_ERROR.raw_text
        assert INVALID_ERROR.detail in retried_conversation[2].parts[0].text
        assert first_call.args[1:] == second_call.args[1:] == ("flag",)
        assert first_call.kwargs == second_call.kwargs == {"suffix": "suffix"}
        assert len(contents) == 1  # the caller's conversation is never mutated
        assert [record.levelno for record in caplog.records] == [logging.DEBUG, logging.WARNING]
        assert caplog.records[-1].__dict__["attempt"] == 2

    @pytest.mark.parametrize("api", [[INVALID_ERROR] * 3], indirect=True)
    async def test__attempts_exhausted__reraises_last_error_and_logs_error(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(GeminiResponseError) as exc_info:
            await Backend(api).request(contents, "flag")

        assert exc_info.value is INVALID_ERROR
        assert api.await_count == gemini_settings.VALIDATION_MAX_RETRIES + 1
        (record,) = caplog.records
        assert record.levelno == logging.ERROR
        assert record.__dict__["failure_kind"] == GeminiFailureKind.SCHEMA_VIOLATION.value
        assert record.__dict__["max_attempts"] == 3

    @pytest.mark.parametrize("api", [[TRUNCATED_ERROR]], indirect=True)
    async def test__non_self_healable_error__is_not_retried(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
    ) -> None:
        with pytest.raises(GeminiResponseError) as exc_info:
            await Backend(api).request(contents, "flag")

        assert exc_info.value is TRUNCATED_ERROR
        assert api.await_count == 1

    @pytest.mark.parametrize("api", [[INVALID_ERROR]], indirect=True)
    async def test__explicit_max_retries__overrides_default(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
    ) -> None:
        with pytest.raises(GeminiResponseError):
            await Backend(api).request_without_retry(contents)

        assert api.await_count == 1

    @pytest.mark.parametrize("api", [[INVALID_RESPONSE, VALID_RESPONSE]], indirect=True)
    async def test__stacked_on_validate_response__heals_end_to_end(
        self,
        api: AsyncMock,
        contents: list[GeminiRequestContent],
    ) -> None:
        result = await Backend(api).request_validated(contents)

        assert result == Answer(value=42)
        assert api.await_count == 2

    def test__negative_max_retries__raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            self_heal(max_retries=-1)

    def test__decorated_method__keeps_its_name(self) -> None:
        assert Backend.request.__name__ == "request"
