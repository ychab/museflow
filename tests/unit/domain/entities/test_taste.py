import pytest

from tests.unit.factories.entities.taste import TasteEraFactory
from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory


class TestTasteProfileSortTimeline:
    @pytest.mark.parametrize(
        ("eras_time_ranges", "expected_order"),
        [
            pytest.param(
                ["unknown to Undated", "2017-01-15 to 2017-01-17", "Contemporary", "2025-10-02 to 2026-01-28"],
                ["Contemporary", "2025-10-02 to 2026-01-28", "2017-01-15 to 2017-01-17", "unknown to Undated"],
                id="mixed_all_cases",
            ),
            pytest.param(
                ["2017-01-15 to 2017-01-17", "Contemporary French Rap", "no date here"],
                ["Contemporary French Rap", "2017-01-15 to 2017-01-17", "no date here"],
                id="contemporary_in_label_and_fallback",
            ),
            pytest.param(
                ["Undated", "unknown", "2020-06-01 to 2021-01-01"],
                ["2020-06-01 to 2021-01-01", "Undated", "unknown"],
                id="undated_and_unknown_variants",
            ),
        ],
    )
    def test__sort_timeline__orders_correctly(self, eras_time_ranges: list[str], expected_order: list[str]) -> None:
        eras = [TasteEraFactory.build(time_range=tr) for tr in eras_time_ranges]
        profile = TasteProfileFactory.build(profile=TasteProfileDataFactory.build(taste_timeline=eras))
        timeline = profile.sort_timeline().profile["taste_timeline"]
        assert [e["time_range"] for e in timeline] == expected_order

    def test__sort_timeline__returns_new_instance(self) -> None:
        eras = [TasteEraFactory.build(time_range="Contemporary")]
        profile = TasteProfileFactory.build(profile=TasteProfileDataFactory.build(taste_timeline=eras))
        sorted_profile = profile.sort_timeline()

        assert sorted_profile is not profile
        assert sorted_profile.id == profile.id
        assert sorted_profile.user_id == profile.user_id
        assert sorted_profile.name == profile.name

    def test__sort_timeline__does_not_mutate_original(self) -> None:
        eras = [
            TasteEraFactory.build(time_range="2025-01-01 to 2025-06-01"),
            TasteEraFactory.build(time_range="Contemporary"),
        ]
        profile = TasteProfileFactory.build(profile=TasteProfileDataFactory.build(taste_timeline=eras))
        original_first = profile.profile["taste_timeline"][0]["time_range"]

        profile.sort_timeline()

        assert profile.profile["taste_timeline"][0]["time_range"] == original_first
