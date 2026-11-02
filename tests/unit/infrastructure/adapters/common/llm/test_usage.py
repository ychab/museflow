from decimal import Decimal

from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter


class TestLLMUsageMeter:
    def test__empty(self) -> None:
        meter = LLMUsageMeter()

        assert meter.usages == []
        assert meter.total_cost == Decimal(0)

    def test__record__sums_per_step_and_model(self) -> None:
        meter = LLMUsageMeter()
        usage = ChatUsage.model_validate(
            {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "completion_tokens_details": {"reasoning_tokens": 150},
                "cost": 0.01,
            }
        )

        meter.record("profiler segment", "google/gemini-2.5-flash", usage)
        meter.record("profiler segment", "google/gemini-2.5-flash", usage)
        meter.record("profiler segment", "openai/gpt-5-mini", ChatUsage(prompt_tokens=10, completion_tokens=5))
        meter.record("profiler merge", "google/gemini-2.5-flash", ChatUsage(cost=Decimal("0.002")))

        assert meter.usages == [
            LLMUsage(
                step="profiler segment",
                model="google/gemini-2.5-flash",
                calls=2,
                prompt_tokens=2000,
                completion_tokens=400,
                reasoning_tokens=300,
                cost=Decimal("0.02"),
            ),
            LLMUsage(
                step="profiler segment",
                model="openai/gpt-5-mini",
                calls=1,
                prompt_tokens=10,
                completion_tokens=5,
            ),
            LLMUsage(step="profiler merge", model="google/gemini-2.5-flash", calls=1, cost=Decimal("0.002")),
        ]
        assert meter.total_cost == Decimal("0.022")
