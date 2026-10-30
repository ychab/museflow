import json
import logging
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError

from museflow.infrastructure.adapters.common.llm.exceptions import LLMFailureKind
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.schemas import ChatCompletionResponse

logger = logging.getLogger(__name__)

_LENGTH_FINISH_REASON = "length"
_REFUSAL_FINISH_REASON = "content_filter"
_RAW_PREVIEW_LENGTH = 200
_DETAIL_LENGTH = 500


def _summarize_validation_error(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or '<root>'}: {err['msg']}"
        for err in error.errors(include_input=False, include_url=False)
    )


def _invalid_response(
    adapter: str,
    failure_kind: LLMFailureKind,
    detail: str,
    raw_text: str,
    finish_reason: str | None,
) -> LLMResponseError:
    detail = detail[:_DETAIL_LENGTH]
    return LLMResponseError(
        f"Invalid LLM response ({failure_kind}): {detail}",
        adapter=adapter,
        failure_kind=failure_kind,
        finish_reason=finish_reason,
        raw_text=raw_text,
        detail=detail,
    )


def _parse[T: BaseModel](response_data: dict[str, Any], response_model: type[T], adapter: str) -> T:
    envelope = ChatCompletionResponse.model_validate(response_data)

    if envelope.error is not None:
        raise LLMResponseError(
            f"LLM provider error: {envelope.error.message}",
            adapter=adapter,
            failure_kind=LLMFailureKind.PROVIDER_ERROR,
            detail=envelope.error.message[:_DETAIL_LENGTH],
        )

    if not envelope.choices:
        raise LLMResponseError("LLM returned no choices", adapter=adapter, failure_kind=LLMFailureKind.NO_CHOICES)

    choice = envelope.choices[0]
    finish_reason = choice.finish_reason
    message = choice.message
    logger.debug(f"LLM {adapter} reply from {envelope.model}", extra={"adapter": adapter, "model": envelope.model})

    if finish_reason == _REFUSAL_FINISH_REASON or (message is not None and message.refusal):
        raise LLMResponseError(
            "LLM refused to answer",
            adapter=adapter,
            failure_kind=LLMFailureKind.REFUSED,
            finish_reason=finish_reason,
            detail=(message.refusal or "") if message else "",
        )

    if finish_reason == _LENGTH_FINISH_REASON:
        raise LLMResponseError(
            "LLM response truncated (length)",
            adapter=adapter,
            failure_kind=LLMFailureKind.TRUNCATED,
            finish_reason=finish_reason,
        )

    if message is None or not message.content:
        raise LLMResponseError(
            "LLM returned an empty response",
            adapter=adapter,
            failure_kind=LLMFailureKind.EMPTY_RESPONSE,
            finish_reason=finish_reason,
        )

    raw_text = message.content
    try:
        return response_model.model_validate(json.loads(raw_text))
    except json.JSONDecodeError as e:
        raise _invalid_response(adapter, LLMFailureKind.INVALID_JSON, str(e), raw_text, finish_reason) from e
    except ValidationError as e:
        raise _invalid_response(
            adapter, LLMFailureKind.SCHEMA_VIOLATION, _summarize_validation_error(e), raw_text, finish_reason
        ) from e


def parse_completion[T: BaseModel](response_data: dict[str, Any], response_model: type[T], adapter: str) -> T:
    """Turns the raw JSON body of a chat completion into `response_model`.

    Fails early and explicitly on provider errors, empty, refused, truncated (`length`), non-JSON or schema-violating
    replies. Every failure is logged as a WARNING.

    Raises:
        LLMResponseError: If the reply is unusable.
    """
    try:
        return _parse(response_data, response_model, adapter)
    except LLMResponseError as e:
        logger.warning(
            f"LLM {adapter} response unusable ({e.failure_kind})",
            extra={
                "adapter": adapter,
                "failure_kind": e.failure_kind.value,
                "finish_reason": e.finish_reason,
                "raw_preview": e.raw_text[:_RAW_PREVIEW_LENGTH],
            },
        )
        raise
