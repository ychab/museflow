from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.common.llm.types import ReasoningEffort
from museflow.infrastructure.config.settings.openrouter import LLMSettings
from museflow.infrastructure.config.settings.openrouter import OpenRouterSettings


class TestOpenRouterSettings:
    def test__defaults(self) -> None:
        settings = OpenRouterSettings(_env_file=None)

        assert settings.ENRICHER == LLMSettings(MODEL="google/gemini-2.5-flash-lite")
        assert settings.ZDR is True

    def test__nested_override__keeps_step_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_ADVISOR__REASONING_EFFORT", "high")
        monkeypatch.setenv("OPENROUTER_ADVISOR__FALLBACK_MODELS", '["openai/gpt-5-mini"]')

        settings = OpenRouterSettings(_env_file=None)

        assert settings.ADVISOR == LLMSettings(
            MODEL="google/gemini-2.5-flash",
            REASONING_EFFORT=ReasoningEffort.HIGH,
            FALLBACK_MODELS=["openai/gpt-5-mini"],
        )
        assert settings.ENRICHER.REASONING_EFFORT is None

    def test__nested_override__model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_PROFILER_REFLECT__MODEL", "anthropic/claude-sonnet-4.5")

        settings = OpenRouterSettings(_env_file=None)

        assert settings.PROFILER_REFLECT.MODEL == "anthropic/claude-sonnet-4.5"

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            pytest.param("OPENROUTER_ENRICHER__REASONING_EFFORT", "extreme", id="unknown_effort"),
            pytest.param("OPENROUTER_ENRICHER__MAX_TOKENS", "0", id="max_tokens_not_positive"),
            pytest.param("OPENROUTER_ENRICHER__TEMPERATURE", "3", id="temperature_out_of_range"),
        ],
    )
    def test__invalid_tuning__raises(self, monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
        monkeypatch.setenv(name, value)

        with pytest.raises(ValidationError):
            OpenRouterSettings(_env_file=None)


class TestLLMSettings:
    def test__with_model__overrides_model_only(self) -> None:
        llm = LLMSettings(MODEL="google/gemini-2.5-flash", MAX_TOKENS=1000)

        assert llm.with_model("openai/gpt-5-mini") == LLMSettings(MODEL="openai/gpt-5-mini", MAX_TOKENS=1000)
        assert llm.MODEL == "google/gemini-2.5-flash"

    def test__with_model__none__unchanged(self) -> None:
        llm = LLMSettings(MODEL="google/gemini-2.5-flash")

        assert llm.with_model(None) is llm
