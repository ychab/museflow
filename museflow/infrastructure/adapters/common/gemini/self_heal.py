import functools
import logging
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Concatenate

from museflow.infrastructure.adapters.common.gemini.exceptions import GeminiResponseError
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.config.settings.gemini import gemini_settings

logger = logging.getLogger(__name__)


def self_heal[T, S, **P](
    *,
    max_retries: int = gemini_settings.VALIDATION_MAX_RETRIES,
) -> Callable[
    [Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]]],
    Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]],
]:
    """Self-healing for Gemini structured outputs, in the spirit of tenacity's `@retry`.

    Meant to wrap a method already decorated with `validate_response`. When Gemini answers with invalid JSON or a
    payload that violates the response model, the method is called again with the conversation extended by Gemini's
    bad answer and the validation error, so that the model can correct itself (up to `max_retries` extra attempts).
    Other failures (truncated, blocked or empty replies) are not retried, and transport errors are left to tenacity
    on `make_api_call`.

    The decorated method must take the conversation (`list[GeminiRequestContent]`) as its first parameter after
    `self`. Removing this decorator disables the behavior without any other change.

    Raises:
        ValueError: If `max_retries` is negative.
        GeminiResponseError: When calling the decorated method, if no valid reply was obtained.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    def decorator(
        func: Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]],
    ) -> Callable[Concatenate[S, list[GeminiRequestContent], P], Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(self: S, contents: list[GeminiRequestContent], /, *args: P.args, **kwargs: P.kwargs) -> T:
            conversation = list(contents)
            max_attempts = max_retries + 1
            attempt = 0

            while True:
                attempt += 1
                try:
                    result = await func(self, conversation, *args, **kwargs)
                except GeminiResponseError as e:
                    if not e.self_healable:
                        raise

                    extra = {
                        "adapter": e.adapter,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "failure_kind": e.failure_kind.value,
                    }
                    if attempt >= max_attempts:
                        logger.error(
                            f"Gemini {e.adapter} self-healing exhausted ({attempt}/{max_attempts})", extra=extra
                        )
                        raise

                    logger.debug(f"Gemini {e.adapter} reply invalid, retrying ({attempt}/{max_attempts})", extra=extra)
                    conversation = [
                        *conversation,
                        GeminiRequestContent(role="model", parts=[GeminiRequestPart(text=e.raw_text)]),
                        GeminiRequestContent(
                            role="user",
                            parts=[
                                GeminiRequestPart(
                                    text=(
                                        f"Your previous response is invalid: {e.detail}. "
                                        "Return only the corrected JSON conforming to the schema."
                                    )
                                )
                            ],
                        ),
                    ]
                else:
                    if attempt > 1:
                        logger.warning(
                            f"Gemini self-healing recovered after {attempt} attempts",
                            extra={"attempt": attempt, "max_attempts": max_attempts},
                        )
                    return result

        return wrapper

    return decorator
