from enum import StrEnum


class LLMFailureKind(StrEnum):
    NO_CHOICES = "no_choices"  # The choices list is empty
    PROVIDER_ERROR = "provider_error"  # An HTTP 200 carrying an error (e.g. the provider failed mid-generation)
    REFUSED = "refused"  # The model refused to answer (content filter or explicit refusal)
    TRUNCATED = "truncated"  # finish_reason is "length": the JSON is cut off
    EMPTY_RESPONSE = "empty_response"  # The message carries no content
    INVALID_JSON = "invalid_json"  # The content is not parseable JSON
    SCHEMA_VIOLATION = "schema_violation"  # The JSON is valid but rejected by the Pydantic model


# Kinds a follow-up message showing the error to the model can fix (see `self_heal`)
_SELF_HEALABLE_KINDS = frozenset({LLMFailureKind.INVALID_JSON, LLMFailureKind.SCHEMA_VIOLATION})


class LLMResponseError(Exception):
    """An LLM reply that could not be turned into the expected model."""

    def __init__(
        self,
        message: str,
        *,
        adapter: str,
        failure_kind: LLMFailureKind,
        finish_reason: str | None = None,
        raw_text: str = "",
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.adapter = adapter
        self.failure_kind = failure_kind
        self.finish_reason = finish_reason
        self.raw_text = raw_text
        self.detail = detail

    @property
    def self_healable(self) -> bool:
        return self.failure_kind in _SELF_HEALABLE_KINDS


class LLMRequestError(Exception):
    """OpenRouter rejected the request (bad parameters, auth, credits, or no provider matching the routing rules)."""

    def __init__(self, message: str, *, adapter: str, model: str, status_code: int) -> None:
        super().__init__(message)
        self.adapter = adapter
        self.model = model
        self.status_code = status_code


class LLMRateLimitError(Exception):
    """OpenRouter kept rate-limiting the request past the retry budget."""
