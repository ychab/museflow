import pytest

from museflow.domain.utils.taste import behavioral_traits_summary
from museflow.domain.utils.taste import core_identity_summary
from museflow.domain.utils.taste import current_era_label
from museflow.domain.utils.taste import era_sort_key
from museflow.domain.utils.taste import oldest_era_label
from museflow.domain.utils.taste import personality_archetype
from museflow.domain.utils.taste import timeline_summary

from tests.unit.factories.entities.taste import TasteEraFactory
from tests.unit.factories.entities.taste import TasteProfileDataFactory


class TestEraSortKey:
    @pytest.mark.parametrize(
        ("time_range", "expected"),
        [
            pytest.param("Contemporary", "9999-99-99", id="contemporary"),
            pytest.param("Contemporary French Rap", "9999-99-99", id="contemporary_with_label"),
            pytest.param("Undated", "0000-00-00", id="undated"),
            pytest.param("unknown to Undated", "0000-00-00", id="unknown_in_range"),
            pytest.param("2021-03-15 to 2022-01-01", "2021-03-15", id="date_extracted"),
            pytest.param("no date here", "0000-00-00", id="no_match_fallback"),
        ],
    )
    def test__nominal(self, time_range: str, expected: str) -> None:
        era = TasteEraFactory.build(time_range=time_range)
        assert era_sort_key(era) == expected


class TestTimelineSummary:
    def test__nominal(self) -> None:
        eras = [
            TasteEraFactory.build(era_label="The Early Days"),
            TasteEraFactory.build(era_label="The Discovery Phase"),
            TasteEraFactory.build(era_label="Now"),
        ]
        profile = TasteProfileDataFactory.build(taste_timeline=eras)
        assert timeline_summary(profile) == "The Early Days → The Discovery Phase → Now"

    def test__empty_timeline(self) -> None:
        profile = TasteProfileDataFactory.build(taste_timeline=[])
        assert timeline_summary(profile) == "No timeline"


class TestCoreIdentitySummary:
    def test__nominal(self) -> None:
        profile = TasteProfileDataFactory.build(
            core_identity={"progressive metal": 0.9, "post-rock": 0.7, "jazz": 0.5}
        )
        result = core_identity_summary(profile)
        assert result == "progressive metal (0.90), post-rock (0.70), jazz (0.50)"

    def test__empty_core_identity(self) -> None:
        profile = TasteProfileDataFactory.build(core_identity={})
        assert core_identity_summary(profile) == "unknown"

    def test__top_n_limits_results(self) -> None:
        profile = TasteProfileDataFactory.build(
            core_identity={"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6, "e": 0.5, "f": 0.4}
        )
        result = core_identity_summary(profile, top_n=2)
        assert result == "a (0.90), b (0.80)"


class TestBehavioralTraitsSummary:
    def test__nominal(self) -> None:
        profile = TasteProfileDataFactory.build(behavioral_traits={"openness": 0.9, "rhythmic_dependency": 0.7})
        result = behavioral_traits_summary(profile)
        assert result == "openness: 0.90, rhythmic_dependency: 0.70"

    def test__empty_behavioral_traits(self) -> None:
        profile = TasteProfileDataFactory.build(behavioral_traits={})
        assert behavioral_traits_summary(profile) == "unknown"


class TestPersonalityArchetype:
    def test__nominal(self) -> None:
        profile = TasteProfileDataFactory.build(personality_archetype="The Digger")
        assert personality_archetype(profile) == "The Digger"

    def test__none_returns_unknown(self) -> None:
        profile = TasteProfileDataFactory.build(personality_archetype=None)
        assert personality_archetype(profile) == "unknown"


class TestOldestEraLabel:
    def test__nominal(self) -> None:
        eras = [
            TasteEraFactory.build(era_label="First Era"),
            TasteEraFactory.build(era_label="Second Era"),
        ]
        profile = TasteProfileDataFactory.build(taste_timeline=eras)
        assert oldest_era_label(profile) == "First Era"

    def test__empty_timeline(self) -> None:
        profile = TasteProfileDataFactory.build(taste_timeline=[])
        assert oldest_era_label(profile) == "earliest era"


class TestCurrentEraLabel:
    def test__nominal(self) -> None:
        eras = [
            TasteEraFactory.build(era_label="First Era"),
            TasteEraFactory.build(era_label="Last Era"),
        ]
        profile = TasteProfileDataFactory.build(taste_timeline=eras)
        assert current_era_label(profile) == "Last Era"

    def test__empty_timeline(self) -> None:
        profile = TasteProfileDataFactory.build(taste_timeline=[])
        assert current_era_label(profile) == "current era"
