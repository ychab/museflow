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


@dataclass(frozen=True, kw_only=True)
class LLMUsageTotals:
    """What a set of command runs spent on LLM calls."""

    runs: int = 0
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost: Decimal = Decimal(0)
    duration: timedelta = timedelta(0)


@dataclass(frozen=True, kw_only=True)
class LLMUsageGroup:
    # One value per grouping, in the requested order. None when the runs have no value for a grouping: no profile
    # (enrich) or a deleted one.
    values: list[str | None]
    totals: LLMUsageTotals


@dataclass(frozen=True, kw_only=True)
class LLMUsageSummary:
    """The LLM usage of a user, per group, with the grand total (no subtotals).

    A run may span several groups (one per step or model), so the total counts its runs on its own.
    """

    groups: list[LLMUsageGroup]
    total: LLMUsageTotals
