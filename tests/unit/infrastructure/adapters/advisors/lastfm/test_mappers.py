import pytest

from museflow.infrastructure.adapters.advisors.lastfm.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmArtist
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmTrack


class TestTrackSuggested:
    @pytest.mark.parametrize(
        ("duration", "expected_duration_ms"),
        [
            (232, 232 * 1000),
            (None, None),
        ],
    )
    def test__duration(self, duration: int | None, expected_duration_ms: int | None) -> None:
        track_lastfm = LastFmTrack(
            name="Mi Pueblo",
            mbid="2ced3803-b87a-319f-9926-0388b20608be",
            artist=LastFmArtist(
                mbid="5436ce22-af50-4714-addc-afd5d2efc77f",
                name="Grupo Niche",
            ),
            match=1.0,
            duration=duration,
        )

        track_suggested = to_track_suggested(track_lastfm)
        assert track_suggested.duration_ms == expected_duration_ms
