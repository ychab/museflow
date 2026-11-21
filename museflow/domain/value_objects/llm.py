from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from museflow.domain.enums import ReasoningEffort


@dataclass(frozen=True, kw_only=True)
class LLMUsage:
    """Tokens, cost and time of the LLM calls of one step on one model."""

    step: str
    model: str
    reasoning_effort: ReasoningEffort
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0  # reasoning tokens included
    reasoning_tokens: int = 0
    cost: Decimal = Decimal(0)
    duration: timedelta = timedelta(0)  # waiting for the replies, retries included
