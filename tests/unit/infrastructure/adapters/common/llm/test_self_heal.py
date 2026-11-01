import logging
from unittest.mock import AsyncMock

from pydantic import BaseModel

import pytest

from museflow.infrastructure.adapters.common.llm.exceptions import LLMFailureKind
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.common.llm.self_heal import self_heal
from museflow.infrastructure.config.settings.openrouter import openrouter_settings

INVALID_ERROR = LLMResponseError(
    "invalid",
    adapter="test",
    failure_kind=LLMFailureKind.SCHEMA_VIOLATION,
    raw_text='{"value": "nope"}',
    detail="value: Input should be a valid integer",
)
TRUNCATED_ERROR = LLMResponseError("truncated", adapter="test", failure_kind=LLMFailureKind.TRUNCATED)


class Answer(BaseModel):
    value: int


class Backend:
    def __init__(self, api: AsyncMock) -> None:
        self.api = api

    @self_heal()
    async def request(self, messages: list[ChatMessage], flag: str, *, suffix: str = "") -> Answer:
        return await self.api(messages, flag, suffix=suffix)  # type: ignore[no-any-return]

    @self_heal(max_retries=0)
    async def request_without_retry(self, messages: list[ChatMessage]) -> Answer:
        return await self.api(messages)  # type: ignore[no-any-return]


class TestSelfHeal:
    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        return [ChatMessage(role="user", content="prompt")]

    @pytest.fixture
    def api(self, request: pytest.FixtureRequest) -> AsyncMock:
        return AsyncMock(side_effect=request.param)

    @pytest.mark.parametrize("api", [[Answer(value=42)]], indirect=True)
    async def test__valid_first_attempt__returns_result_and_forwards_arguments(
        self,
        api: AsyncMock,
        messages: list[ChatMessage],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            result = await Backend(api).request(messages, "flag", suffix="suffix")

        assert result == Answer(value=42)
        api.assert_awaited_once_with(messages, "flag", suffix="suffix")
        assert caplog.records == []

    @pytest.mark.parametrize("api", [[INVALID_ERROR, Answer(value=42)]], indirect=True)
    async def test__invalid_then_valid__retries_with_feedback_and_logs_recovery(
        self,
        api: AsyncMock,
        messages: list[ChatMessage],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            result = await Backend(api).request(messages, "flag", suffix="suffix")

        assert result == Answer(value=42)
        first_call, second_call = api.await_args_list
        assert first_call.args[0] == messages
        retried_conversation: list[ChatMessage] = second_call.args[0]
        assert [message.role for message in retried_conversation] == ["user", "assistant", "user"]
        assert retried_conversation[1].content == INVALID_ERROR.raw_text
        assert INVALID_ERROR.detail in retried_conversation[2].content
        assert first_call.args[1:] == second_call.args[1:] == ("flag",)
        assert first_call.kwargs == second_call.kwargs == {"suffix": "suffix"}
        assert len(messages) == 1  # the caller's conversation is never mutated
        assert [record.levelno for record in caplog.records] == [logging.DEBUG, logging.WARNING]
        assert caplog.records[-1].__dict__["attempt"] == 2

    @pytest.mark.parametrize("api", [[INVALID_ERROR] * 3], indirect=True)
    async def test__attempts_exhausted__reraises_last_error_and_logs_error(
        self,
        api: AsyncMock,
        messages: list[ChatMessage],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(LLMResponseError) as exc_info:
            await Backend(api).request(messages, "flag")

        assert exc_info.value is INVALID_ERROR
        assert api.await_count == openrouter_settings.VALIDATION_MAX_RETRIES + 1
        (record,) = caplog.records
        assert record.levelno == logging.ERROR
        assert record.__dict__["failure_kind"] == LLMFailureKind.SCHEMA_VIOLATION.value
        assert record.__dict__["max_attempts"] == 3

    @pytest.mark.parametrize("api", [[TRUNCATED_ERROR]], indirect=True)
    async def test__non_self_healable_error__is_not_retried(
        self,
        api: AsyncMock,
        messages: list[ChatMessage],
    ) -> None:
        with pytest.raises(LLMResponseError) as exc_info:
            await Backend(api).request(messages, "flag")

        assert exc_info.value is TRUNCATED_ERROR
        assert api.await_count == 1

    @pytest.mark.parametrize("api", [[INVALID_ERROR]], indirect=True)
    async def test__explicit_max_retries__overrides_default(
        self,
        api: AsyncMock,
        messages: list[ChatMessage],
    ) -> None:
        with pytest.raises(LLMResponseError):
            await Backend(api).request_without_retry(messages)

        assert api.await_count == 1

    def test__negative_max_retries__raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            self_heal(max_retries=-1)

    def test__decorated_method__keeps_its_name(self) -> None:
        assert Backend.request.__name__ == "request"
