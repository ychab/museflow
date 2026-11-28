import dataclasses
import time
from datetime import timedelta
from decimal import Decimal

from museflow.domain.enums import ReasoningEffort
from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage


class LLMUsageMeter:
    """Sums the usage OpenRouter reports for each reply, per step and model, over one command run.

    Created when the command starts, it also times the whole run. Besides the whole run, it keeps what was not popped
    yet, which the use case saves batch by batch.
    """

    def __init__(self) -> None:
        self._run_usages: dict[tuple[str, str], LLMUsage] = {}
        self._pending: dict[tuple[str, str], LLMUsage] = {}
        self._started_at = time.monotonic()

    @property
    def run_usages(self) -> list[LLMUsage]:
        return list(self._run_usages.values())

    @property
    def total_cost(self) -> Decimal:
        return sum((usage.cost for usage in self._run_usages.values()), Decimal(0))

    @property
    def elapsed(self) -> timedelta:
        return timedelta(seconds=time.monotonic() - self._started_at)

    def record(
        self,
        step: str,
        model: str,
        reasoning_effort: ReasoningEffort,
        usage: ChatUsage,
        duration: timedelta,
    ) -> None:
        for usages in (self._run_usages, self._pending):
            self._add(usages, step, model, reasoning_effort, usage, duration)

    def pop_usages(self) -> list[LLMUsage]:
        """What was recorded since the last pop, per step and model; the next pop starts afresh."""
        popped = list(self._pending.values())
        self._pending.clear()
        return popped

    def _add(
        self,
        usages: dict[tuple[str, str], LLMUsage],
        step: str,
        model: str,
        reasoning_effort: ReasoningEffort,
        usage: ChatUsage,
        duration: timedelta,
    ) -> None:
        # A step runs on one setting through a command run: the effort comes with the step, it needs no key of its own.
        current = usages.get(
            (step, model),
            LLMUsage(step=step, model=model, reasoning_effort=reasoning_effort),
        )
        details = usage.completion_tokens_details
        usages[(step, model)] = dataclasses.replace(
            current,
            calls=current.calls + 1,
            prompt_tokens=current.prompt_tokens + usage.prompt_tokens,
            completion_tokens=current.completion_tokens + usage.completion_tokens,
            reasoning_tokens=current.reasoning_tokens + ((details.reasoning_tokens or 0) if details else 0),
            cost=current.cost + (usage.cost or Decimal(0)),
            duration=current.duration + duration,
        )
