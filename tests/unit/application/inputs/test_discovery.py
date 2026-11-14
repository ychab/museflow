import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.domain.enums import DiscoveryFocus


class TestDiscoverTasteConfigInput:
    @pytest.mark.parametrize("max_attempts", [0, -1])
    def test__max_attempts__below_one(self, max_attempts: int) -> None:
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            DiscoverTasteConfigInput(max_attempts=max_attempts)

    @pytest.mark.parametrize("artist_tracks_concurrency", [0, -1])
    def test__artist_tracks_concurrency__below_one(self, artist_tracks_concurrency: int) -> None:
        with pytest.raises(ValueError, match="artist_tracks_concurrency must be at least 1"):
            DiscoverTasteConfigInput(artist_tracks_concurrency=artist_tracks_concurrency)

    @pytest.mark.parametrize("favourite_artists_limit", [0, -1])
    def test__favourite_artists_limit__below_one(self, favourite_artists_limit: int) -> None:
        with pytest.raises(ValueError, match="favourite_artists_limit must be at least 1"):
            DiscoverTasteConfigInput(favourite_artists_limit=favourite_artists_limit)

    @pytest.mark.parametrize("favourite_artists_per_attempt", [0, -1])
    def test__favourite_artists_per_attempt__below_one(self, favourite_artists_per_attempt: int) -> None:
        with pytest.raises(ValueError, match="favourite_artists_per_attempt must be at least 1"):
            DiscoverTasteConfigInput(favourite_artists_per_attempt=favourite_artists_per_attempt)

    @pytest.mark.parametrize(
        ("prompt", "focus", "expected_focus"),
        [
            pytest.param(None, None, DiscoveryFocus.EXPANSION, id="no_prompt__default"),
            pytest.param("", None, DiscoveryFocus.EXPANSION, id="empty_prompt__default"),
            pytest.param("lo-fi jazz", None, None, id="prompt__no_focus"),
            pytest.param(
                "lo-fi jazz", DiscoveryFocus.CULTURAL_BRIDGE, DiscoveryFocus.CULTURAL_BRIDGE, id="prompt__focus"
            ),
        ],
    )
    def test__focus__resolved(
        self,
        prompt: str | None,
        focus: DiscoveryFocus | None,
        expected_focus: DiscoveryFocus | None,
    ) -> None:
        assert DiscoverTasteConfigInput(prompt=prompt, focus=focus).focus == expected_focus
