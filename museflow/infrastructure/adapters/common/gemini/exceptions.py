from enum import StrEnum


class GeminiFailureKind(StrEnum):
    NO_CANDIDATES = "no_candidates"  # The candidates list is empty (e.g. blocked by safety filters)
    EMPTY_RESPONSE = "empty_response"  # The candidate carries no text part
    TRUNCATED = "truncated"  # finishReason is MAX_TOKENS: the JSON is cut off
    INVALID_JSON = "invalid_json"  # The text is not parseable JSON
    SCHEMA_VIOLATION = "schema_violation"  # The JSON is valid but rejected by the Pydantic model


# Kinds a follow-up message showing the error to the model can fix (see `self_heal`)
_SELF_HEALABLE_KINDS = frozenset({GeminiFailureKind.INVALID_JSON, GeminiFailureKind.SCHEMA_VIOLATION})


class GeminiResponseError(Exception):
    """A Gemini reply that could not be turned into the expected model."""

    def __init__(
        self,
        message: str,
        *,
        adapter: str,
        failure_kind: GeminiFailureKind,
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
