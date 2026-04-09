import pytest

from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.music import TrackFactory


@pytest.mark.wiremock("gemini")
class TestGeminiTasteProfileAdapter:
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
        gemini_profiler: GeminiTasteProfileAdapter,
    ) -> None:
        profile = await gemini_profiler.build_profile_segment(tracks)

        assert profile == TasteProfileDataFactory.build(
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
            core_identity={"indie rock": 0.8},
            current_vibe={"indie rock": 0.9},
            personality_archetype=None,
            life_phase_insights=[],
            musical_identity_summary=None,
            behavioral_traits={},
            discovery_style=None,
        )

    async def test__merge_profiles__nominal(
        self,
        profile_data: TasteProfileData,
        gemini_profiler: GeminiTasteProfileAdapter,
    ) -> None:
        profile_merged = await gemini_profiler.merge_profiles(profile_data, profile_data)

        assert profile_merged == TasteProfileDataFactory.build(
            taste_timeline=[
                {
                    "era_label": "Indie Exploration",
                    "time_range": "2021-2022",
                    "technical_fingerprint": {
                        "energy": 0.7,
                        "acousticness": 0.6,
                        "rhythmic_complexity": 0.4,
                        "atmospheric": 0.5,
                        "instrumentalness": 0.2,
                    },
                    "dominant_moods": ["melancholic"],
                },
                {
                    "era_label": "Electronic Drift",
                    "time_range": "2022-2023",
                    "technical_fingerprint": {
                        "energy": 0.85,
                        "acousticness": 0.1,
                        "rhythmic_complexity": 0.5,
                        "atmospheric": 0.4,
                        "instrumentalness": 0.3,
                    },
                    "dominant_moods": ["euphoric"],
                },
            ],
            core_identity={"indie rock": 0.75, "electronic": 0.4},
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
        gemini_profiler: GeminiTasteProfileAdapter,
    ) -> None:
        profile_reflected = await gemini_profiler.reflect_on_profile(profile_data)

        assert profile_reflected == TasteProfileDataFactory.build(
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
            core_identity={"indie rock": 0.8},
            current_vibe={"indie rock": 0.9},
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
