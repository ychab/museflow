import pytest

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.track import Track
from museflow.infrastructure.adapters.profilers.openrouter.client import OpenRouterTasteProfileAdapter

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteEraFactory
from tests.unit.factories.entities.track import TrackFactory


@pytest.mark.wiremock("openrouter")
class TestOpenRouterTasteProfileAdapter:
    @pytest.fixture
    def tracks(self) -> list[Track]:
        return TrackFactory.batch(3)

    @pytest.fixture
    def profile_data(self) -> TasteProfileData:
        return TasteProfileDataFactory.build(
            personality_archetype=None,
            life_phase_insights=[],
        )

    async def test__build_profile_segment__nominal(
        self,
        tracks: list[Track],
        openrouter_profiler: OpenRouterTasteProfileAdapter,
    ) -> None:
        profile = await openrouter_profiler.build_profile_segment(tracks)

        assert profile == TasteProfileData(
            taste_timeline=[
                {
                    "era_label": "Indie Exploration",
                    "time_range": "2021-2023",
                    "technical_fingerprint": {
                        "energy": 0.7,
                        "acousticness": 0.6,
                        "rhythmic_complexity": 0.4,
                        "atmospheric": 0.5,
                        "instrumentalness": 0.2,
                    },
                    "dominant_moods": ["melancholic"],
                }
            ],
            core_identity={"indie-rock": 0.8},
            current_vibe={"indie-rock": 0.9},
            personality_archetype=None,
            life_phase_insights=[],
            musical_identity_summary=None,
            behavioral_traits={},
            discovery_style=None,
        )

    async def test__merge_profiles__nominal(self, openrouter_profiler: OpenRouterTasteProfileAdapter) -> None:
        foundation = TasteProfileDataFactory.build(
            taste_timeline=[TasteEraFactory.build(time_range="2021-01-01 to 2021-06-30")],
            core_identity={"indie-rock": 0.8, "melancholic": 0.5},
            current_vibe={"indie-rock": 0.9},
        )
        segment = TasteProfileDataFactory.build(
            taste_timeline=[TasteEraFactory.build(time_range="2021-07-01 to 2021-12-31")],
            core_identity={"indie-rock": 0.2, "electronic": 0.6},
            current_vibe={"electronic": 0.8},
        )

        # The stubbed model answers absorb: false, so the segment's era is appended
        profile_merged = await openrouter_profiler.merge_profiles(foundation, segment, 0.3)

        assert profile_merged == TasteProfileData(
            taste_timeline=[foundation["taste_timeline"][0], segment["taste_timeline"][0]],
            core_identity={"indie-rock": 0.62, "melancholic": 0.35, "electronic": 0.18},
            current_vibe={"electronic": 0.8},
            personality_archetype=None,
            life_phase_insights=[],
            musical_identity_summary=None,
            behavioral_traits={},
            discovery_style=None,
        )

    async def test__reflect_on_profile__nominal(
        self,
        profile_data: TasteProfileData,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
    ) -> None:
        profile_reflected = await openrouter_profiler.reflect_on_profile(profile_data)

        assert profile_reflected == TasteProfileData(
            taste_timeline=[
                {
                    "era_label": "Indie Exploration",
                    "time_range": "2021-2023",
                    "technical_fingerprint": {
                        "energy": 0.7,
                        "acousticness": 0.6,
                        "rhythmic_complexity": 0.4,
                        "atmospheric": 0.5,
                        "instrumentalness": 0.2,
                    },
                    "dominant_moods": ["melancholic"],
                }
            ],
            core_identity={"indie-rock": 0.8},
            current_vibe={"indie-rock": 0.9},
            personality_archetype="The Introspective Wanderer",
            life_phase_insights=["Transition from high-energy rock to ambient introspection during 2022"],
            musical_identity_summary=(
                "From melancholic indie strumming to pulsing electronic drift, this listener has quietly shed skins "
                "every two years. The arc is less a genre journey than a search for emotional precision."
            ),
            behavioral_traits={
                "openness": 0.8,
                "adventurousness": 0.7,
                "nostalgia_bias": 0.4,
                "rhythmic_dependency": 0.6,
            },
            discovery_style="The Deep Diver",
        )
