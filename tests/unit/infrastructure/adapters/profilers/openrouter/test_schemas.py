from typing import Any

from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.profilers.openrouter.schemas import TASTE_PROFILE_SCHEMA
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TasteEra
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TasteProfileResponse
from museflow.infrastructure.adapters.profilers.openrouter.schemas import split_weights

from tests.integration.factories.models.taste import TasteProfileDataFactory

_BASE_FINGERPRINT: dict[str, float] = {
    "energy": 0.5,
    "acousticness": 0.5,
    "rhythmic_complexity": 0.5,
    "atmospheric": 0.5,
    "instrumentalness": 0.5,
}

_BASE_ERA: dict[str, Any] = {
    "era_label": "Test Era",
    "time_range": "2020-2021",
    "technical_fingerprint": _BASE_FINGERPRINT,
    "dominant_moods": [],
}

_BASE_PROFILE: dict[str, Any] = {
    "taste_timeline": [_BASE_ERA],
    "core_identity": {"genre_macro": [{"key": "rock", "value": 0.8}]},
    "current_vibe": {"mood": [{"key": "energetic", "value": 0.6}]},
    "personality_archetype": None,
    "life_phase_insights": [],
}


class TestTasteEra:
    def test__dominant_moods__keeps_valid_mood_tags(self) -> None:
        era = TasteEra.model_validate({**_BASE_ERA, "dominant_moods": ["melancholic", "energetic"]})
        assert era.dominant_moods == ["melancholic", "energetic"]

    def test__dominant_moods__filters_invalid_strings(self) -> None:
        era = TasteEra.model_validate({**_BASE_ERA, "dominant_moods": ["melancholic", "ambient vibes", "energetic"]})
        assert era.dominant_moods == ["melancholic", "energetic"]

    def test__dominant_moods__non_list_returns_empty(self) -> None:
        era = TasteEra.model_validate({**_BASE_ERA, "dominant_moods": "melancholic"})
        assert era.dominant_moods == []


class TestTasteProfileResponse:
    @pytest.mark.parametrize(
        "core_identity",
        [
            pytest.param([{"key": "indie-rock", "value": 0.8}], id="flat_list"),
            pytest.param({"indie-rock": 0.8}, id="flat_map"),
        ],
    )
    def test__from_weighted_tiers__rejects_untiered(self, core_identity: object) -> None:
        profile = TasteProfileDataFactory.build()
        with pytest.raises(ValidationError, match="expected an object of {key, value} lists per tier"):
            TasteProfileResponse.model_validate({**profile, "core_identity": core_identity})

    def test__from_weighted_tiers__flattens_tiers(self) -> None:
        content = TasteProfileResponse.model_validate(
            {
                **_BASE_PROFILE,
                "core_identity": {
                    "genre_macro": [{"key": "rock", "value": 0.8}],
                    "genre_meso": [{"key": "indie-rock", "value": 0.7}],
                    "genre_micro": [],
                    "mood": [{"key": "melancholic", "value": 0.4}],
                },
            }
        )
        assert content.core_identity == {"rock": 0.8, "indie-rock": 0.7, "melancholic": 0.4}

    def test__core_identity__filters_invalid_keys(self) -> None:
        content = TasteProfileResponse.model_validate(
            {
                **_BASE_PROFILE,
                "core_identity": {
                    "genre_macro": [
                        {"key": "rock", "value": 0.8},
                        {"key": "free form nonsense", "value": 0.5},
                    ],
                },
            }
        )
        assert content.core_identity == {"rock": 0.8}

    def test__current_vibe__accepts_valid_mood_key(self) -> None:
        content = TasteProfileResponse.model_validate(
            {**_BASE_PROFILE, "current_vibe": {"mood": [{"key": "melancholic", "value": 0.7}]}}
        )
        assert content.current_vibe == {"melancholic": 0.7}

    def test__core_identity__filters_all_invalid_keys(self) -> None:
        content = TasteProfileResponse.model_validate(
            {**_BASE_PROFILE, "core_identity": {"genre_micro": [{"key": "made up genre", "value": 0.9}]}}
        )
        assert content.core_identity == {}

    def test__behavioral_traits__null_becomes_empty(self) -> None:
        content = TasteProfileResponse.model_validate({**_BASE_PROFILE, "behavioral_traits": None})
        assert content.behavioral_traits == {}


class TestSplitWeights:
    def test__groups_by_tier(self) -> None:
        assert split_weights({"rock": 0.8, "indie-rock": 0.7, "afro rap": 0.5, "melancholic": 0.4}) == {
            "genre_macro": [{"key": "rock", "value": 0.8}],
            "genre_meso": [{"key": "indie-rock", "value": 0.7}],
            "genre_micro": [{"key": "afro rap", "value": 0.5}],
            "mood": [{"key": "melancholic", "value": 0.4}],
        }

    def test__tag_in_two_tiers__first_tier_wins(self) -> None:
        assert split_weights({"romantic": 0.6})["genre_meso"] == [{"key": "romantic", "value": 0.6}]
        assert split_weights({"romantic": 0.6})["mood"] == []

    def test__unknown_tag__dropped(self) -> None:
        assert all(items == [] for items in split_weights({"made up genre": 0.9}).values())

    def test__round_trip(self) -> None:
        weights = {"rock": 0.8, "indie-rock": 0.7, "melancholic": 0.4}
        content = TasteProfileResponse.model_validate({**_BASE_PROFILE, "core_identity": split_weights(weights)})
        assert content.core_identity == weights


class TestTasteProfileSchema:
    def test__strict__all_properties_required(self) -> None:
        assert TASTE_PROFILE_SCHEMA.properties is not None
        assert TASTE_PROFILE_SCHEMA.required == list(TASTE_PROFILE_SCHEMA.properties)
        assert TASTE_PROFILE_SCHEMA.additionalProperties is False

    def test__reflection_fields__nullable(self) -> None:
        assert TASTE_PROFILE_SCHEMA.properties is not None
        for name in ("personality_archetype", "musical_identity_summary", "behavioral_traits", "discovery_style"):
            assert "null" in (TASTE_PROFILE_SCHEMA.properties[name].type or [])

    @pytest.mark.parametrize("name", ["core_identity", "current_vibe"])
    def test__weights__one_list_per_tier(self, name: str) -> None:
        assert TASTE_PROFILE_SCHEMA.properties is not None
        weights = TASTE_PROFILE_SCHEMA.properties[name]
        assert weights.required == ["genre_macro", "genre_meso", "genre_micro", "mood"]
