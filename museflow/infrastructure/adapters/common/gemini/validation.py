import functools
import json
import logging
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any
from typing import Concatenate

from pydantic import BaseModel
from pydantic import ValidationError

from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiFailureKind
from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiResponseError
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse

logger = logging.getLogger(__name__)

_MAX_TOKENS_FINISH_REASON = "MAX_TOKENS"
_RAW_PREVIEW_LENGTH = 200
_DETAIL_LENGTH = 500


def _summarize_validation_error(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or '<root>'}: {err['msg']}"
        for err in error.errors(include_input=False, include_url=False)
    )


def _invalid_response(
    adapter: str,
    failure_kind: GeminiFailureKind,
    detail: str,
    raw_text: str,
    finish_reason: str | None,
) -> GeminiResponseError:
    detail = detail[:_DETAIL_LENGTH]
    return GeminiResponseError(
        f"Invalid Gemini response ({failure_kind}): {detail}",
        adapter=adapter,
        failure_kind=failure_kind,
        finish_reason=finish_reason,
        raw_text=raw_text,
        detail=detail,
    )


def _parse[T: BaseModel](response_data: dict[str, Any], response_model: type[T], adapter: str) -> T:
    envelope = GeminiResponse.model_validate(response_data)

    if not envelope.candidates:
        raise GeminiResponseError(
            "Gemini returned no candidates", adapter=adapter, failure_kind=GeminiFailureKind.NO_CANDIDATES
        )

    candidate = envelope.candidates[0]
    finish_reason = candidate.finishReason

    if finish_reason == _MAX_TOKENS_FINISH_REASON:
        raise GeminiResponseError(
            "Gemini response truncated (MAX_TOKENS)",
            adapter=adapter,
            failure_kind=GeminiFailureKind.TRUNCATED,
            finish_reason=finish_reason,
        )

    if candidate.content is None or not candidate.content.parts or not candidate.content.parts[0].text:
        raise GeminiResponseError(
            "Gemini returned an empty response",
            adapter=adapter,
            failure_kind=GeminiFailureKind.EMPTY_RESPONSE,
            finish_reason=finish_reason,
        )

    raw_text = candidate.content.parts[0].text
    try:
        return response_model.model_validate(json.loads(raw_text))
    except json.JSONDecodeError as e:
        raise _invalid_response(adapter, GeminiFailureKind.INVALID_JSON, str(e), raw_text, finish_reason) from e
    except ValidationError as e:
        raise _invalid_response(
            adapter, GeminiFailureKind.SCHEMA_VIOLATION, _summarize_validation_error(e), raw_text, finish_reason
        ) from e


def validate_response[T: BaseModel, S, **P](
    response_model: type[T],
    *,
    adapter: str,
) -> Callable[
    [Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[dict[str, Any]]]],
    Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]],
]:
    """Parses and validates the raw JSON body returned by a Gemini request method.

    The decorated method sends the given conversation (its first parameter after `self`) to Gemini and returns the
    raw JSON body. The decorator turns it into `response_model`, failing early and explicitly on empty, blocked,
    truncated (`MAX_TOKENS`), non-JSON or schema-violating replies. Every failure is logged as a WARNING.

    Raises:
        GeminiResponseError: When calling the decorated method, if the reply is unusable.
    """

    def decorator(
        func: Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[dict[str, Any]]],
    ) -> Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(self: S, contents: list[GeminiRequestContent], *args: P.args, **kwargs: P.kwargs) -> T:
            response_data = await func(self, contents, *args, **kwargs)
            try:
                return _parse(response_data, response_model, adapter)
            except GeminiResponseError as e:
                logger.warning(
                    f"Gemini {adapter} response unusable ({e.failure_kind})",
                    extra={
                        "adapter": adapter,
                        "failure_kind": e.failure_kind.value,
                        "finish_reason": e.finish_reason,
                        "raw_preview": e.raw_text[:_RAW_PREVIEW_LENGTH],
                    },
                )
                raise

        return wrapper

    return decorator
