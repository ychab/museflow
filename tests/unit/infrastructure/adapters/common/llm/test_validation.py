import logging
from typing import Any

from pydantic import BaseModel

import pytest

from museflow.infrastructure.adapters.common.llm.exceptions import LLMFailureKind
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.validation import parse_completion


class Answer(BaseModel):
    value: int


VALID_RESPONSE: dict[str, Any] = {
    "model": "google/gemini-2.5-flash",
    "choices": [{"message": {"role": "assistant", "content": '{"value": 42}'}, "finish_reason": "stop"}],
}


class TestParseCompletion:
    def test__valid_reply__returns_model_and_logs_used_model(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG):
            result = parse_completion(VALID_RESPONSE, Answer, "test")

        assert result == Answer(value=42)
        (record,) = caplog.records
        assert record.levelno == logging.DEBUG
        assert record.__dict__["model"] == "google/gemini-2.5-flash"

    @pytest.mark.parametrize(
        ("response_data", "expected_kind", "expected_finish_reason", "expected_detail"),
        [
            pytest.param(
                {"error": {"code": 502, "message": "Provider returned error"}},
                LLMFailureKind.PROVIDER_ERROR,
                None,
                "Provider returned error",
                id="provider_error",
            ),
            pytest.param({"choices": []}, LLMFailureKind.NO_CHOICES, None, "", id="no_choices"),
            pytest.param({}, LLMFailureKind.NO_CHOICES, None, "", id="no_choices_key"),
            pytest.param(
                {"choices": [{"message": {"content": None}, "finish_reason": "content_filter"}]},
                LLMFailureKind.REFUSED,
                "content_filter",
                "",
                id="content_filter",
            ),
            pytest.param(
                {"choices": [{"finish_reason": "content_filter"}]},
                LLMFailureKind.REFUSED,
                "content_filter",
                "",
                id="content_filter_no_message",
            ),
            pytest.param(
                {"choices": [{"message": {"refusal": "I can't help with that"}, "finish_reason": "stop"}]},
                LLMFailureKind.REFUSED,
                "stop",
                "I can't help with that",
                id="refusal",
            ),
            pytest.param(
                {"choices": [{"message": {"content": '{"value": 4'}, "finish_reason": "length"}]},
                LLMFailureKind.TRUNCATED,
                "length",
                "",
                id="truncated",
            ),
            pytest.param(
                {"choices": [{"finish_reason": "stop"}]}, LLMFailureKind.EMPTY_RESPONSE, "stop", "", id="no_message"
            ),
            pytest.param(
                {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
                LLMFailureKind.EMPTY_RESPONSE,
                "stop",
                "",
                id="empty_content",
            ),
        ],
    )
    def test__unusable_reply__raises_non_self_healable_error(
        self,
        response_data: dict[str, Any],
        expected_kind: LLMFailureKind,
        expected_finish_reason: str | None,
        expected_detail: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING), pytest.raises(LLMResponseError) as exc_info:
            parse_completion(response_data, Answer, "test")

        assert exc_info.value.adapter == "test"
        assert exc_info.value.failure_kind == expected_kind
        assert exc_info.value.finish_reason == expected_finish_reason
        assert exc_info.value.detail == expected_detail
        assert not exc_info.value.self_healable
        (record,) = caplog.records
        assert record.levelno == logging.WARNING
        assert record.__dict__["adapter"] == "test"
        assert record.__dict__["failure_kind"] == expected_kind.value
        assert record.__dict__["finish_reason"] == expected_finish_reason

    @pytest.mark.parametrize(
        ("response_data", "expected_kind", "expected_raw", "expected_detail"),
        [
            pytest.param(
                {"choices": [{"message": {"content": '{"value": 4'}, "finish_reason": "stop"}]},
                LLMFailureKind.INVALID_JSON,
                '{"value": 4',
                "Expecting",
                id="invalid_json",
            ),
            pytest.param(
                {"choices": [{"message": {"content": '{"value": "nope"}'}, "finish_reason": "stop"}]},
                LLMFailureKind.SCHEMA_VIOLATION,
                '{"value": "nope"}',
                "value:",
                id="schema_violation",
            ),
        ],
    )
    def test__invalid_reply__raises_self_healable_error_with_raw_text(
        self,
        response_data: dict[str, Any],
        expected_kind: LLMFailureKind,
        expected_raw: str,
        expected_detail: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING), pytest.raises(LLMResponseError) as exc_info:
            parse_completion(response_data, Answer, "test")

        assert exc_info.value.failure_kind == expected_kind
        assert exc_info.value.finish_reason == "stop"
        assert exc_info.value.raw_text == expected_raw
        assert expected_detail in exc_info.value.detail
        assert exc_info.value.self_healable
        assert caplog.records[0].__dict__["raw_preview"] == expected_raw
