import dataclasses
import time
from datetime import timedelta
from decimal import Decimal

from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage


class LLMUsageMeter:
    """Sums the usage OpenRouter reports for each reply, per step and model, over one command run.

    Created when the command starts, it also times the whole run.
    """

    def __init__(self) -> None:
        self._usages: dict[tuple[str, str], LLMUsage] = {}
        self._started_at = time.monotonic()

    @property
    def usages(self) -> list[LLMUsage]:
        return list(self._usages.values())

    @property
    def total_cost(self) -> Decimal:
        return sum((usage.cost for usage in self._usages.values()), Decimal(0))

    @property
    def elapsed(self) -> timedelta:
        return timedelta(seconds=time.monotonic() - self._started_at)

    def record(self, step: str, model: str, usage: ChatUsage, duration: timedelta) -> None:
        current = self._usages.get((step, model), LLMUsage(step=step, model=model))
        details = usage.completion_tokens_details
        self._usages[(step, model)] = dataclasses.replace(
            current,
            calls=current.calls + 1,
            prompt_tokens=current.prompt_tokens + usage.prompt_tokens,
            completion_tokens=current.completion_tokens + usage.completion_tokens,
            reasoning_tokens=current.reasoning_tokens + ((details.reasoning_tokens or 0) if details else 0),
            cost=current.cost + (usage.cost or Decimal(0)),
            duration=current.duration + duration,
        )
