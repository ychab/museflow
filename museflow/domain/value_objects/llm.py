from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, kw_only=True)
class LLMUsage:
    """Tokens and cost of the LLM calls of one step on one model."""

    step: str
    model: str
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0  # reasoning tokens included
    reasoning_tokens: int = 0
    cost: Decimal = Decimal(0)
