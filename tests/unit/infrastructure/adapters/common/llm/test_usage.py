from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from museflow.domain.enums import ReasoningEffort
from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter


class TestLLMUsageMeter:
    def test__empty(self) -> None:
        meter = LLMUsageMeter()

        assert meter.run_usages == []
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

        second = timedelta(seconds=1)
        meter.record("profiler segment", "google/gemini-2.5-flash", ReasoningEffort.MINIMAL, usage, 2 * second)
        meter.record("profiler segment", "google/gemini-2.5-flash", ReasoningEffort.MINIMAL, usage, 3 * second)
        meter.record(
            "profiler segment",
            "openai/gpt-5-mini",
            ReasoningEffort.MINIMAL,
            ChatUsage(prompt_tokens=10, completion_tokens=5),
            second,
        )
        meter.record(
            "profiler merge",
            "google/gemini-2.5-flash",
            ReasoningEffort.LOW,
            ChatUsage(cost=Decimal("0.002")),
            second,
        )

        assert meter.run_usages == [
            LLMUsage(
                step="profiler segment",
                model="google/gemini-2.5-flash",
                reasoning_effort=ReasoningEffort.MINIMAL,
                calls=2,
                prompt_tokens=2000,
                completion_tokens=400,
                reasoning_tokens=300,
                cost=Decimal("0.02"),
                duration=5 * second,
            ),
            LLMUsage(
                step="profiler segment",
                model="openai/gpt-5-mini",
                reasoning_effort=ReasoningEffort.MINIMAL,
                calls=1,
                prompt_tokens=10,
                completion_tokens=5,
                duration=second,
            ),
            LLMUsage(
                step="profiler merge",
                model="google/gemini-2.5-flash",
                reasoning_effort=ReasoningEffort.LOW,
                calls=1,
                cost=Decimal("0.002"),
                duration=second,
            ),
        ]
        assert meter.total_cost == Decimal("0.022")

    def test__pop_usages__only_what_was_not_taken(self) -> None:
        meter = LLMUsageMeter()
        usage = ChatUsage(prompt_tokens=10, completion_tokens=5, cost=Decimal("0.001"))
        second = timedelta(seconds=1)
        meter.record("enricher", "google/gemini-2.5-flash-lite", ReasoningEffort.MINIMAL, usage, second)

        first = meter.pop_usages()
        meter.record("enricher", "google/gemini-2.5-flash-lite", ReasoningEffort.MINIMAL, usage, second)
        meter.record("enricher", "google/gemini-2.5-flash-lite", ReasoningEffort.MINIMAL, usage, second)

        expected = LLMUsage(
            step="enricher",
            model="google/gemini-2.5-flash-lite",
            reasoning_effort=ReasoningEffort.MINIMAL,
            calls=1,
            prompt_tokens=10,
            completion_tokens=5,
            cost=Decimal("0.001"),
            duration=second,
        )
        assert first == [expected]
        assert meter.pop_usages() == [
            replace(
                expected, calls=2, prompt_tokens=20, completion_tokens=10, cost=Decimal("0.002"), duration=2 * second
            )
        ]
        assert meter.pop_usages() == []
        # The whole run stays for the command's output
        [total] = meter.run_usages
        assert total.calls == 3
        assert meter.total_cost == Decimal("0.003")
