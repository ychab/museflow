from typing import Any

from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmSimilarTracksResponse


class TestLastFmSimilarTracksResponse:
    def test__similar_track__not_list(self) -> None:
        payload: dict[str, Any] = {
            "similartracks": {
                "track": {
                    "artist": {
                        "mbid": "5436ce22-af50-4714-addc-afd5d2efc77f",
                        "name": "Grupo Niche",
                    },
                    "match": 1.0,
                    "mbid": "2ced3803-b87a-319f-9926-0388b20608be",
                    "name": "Mi Pueblo",
                    "duration": 3 * 60,
                },
            },
        }

        page = LastFmSimilarTracksResponse.model_validate(payload)
        assert page.similartracks is not None
        assert isinstance(page.similartracks.track, list)

        track = page.similartracks.track[0]
        assert track.mbid == "2ced3803-b87a-319f-9926-0388b20608be"
        assert track.name == "Mi Pueblo"
        assert track.match == 1.0
        assert track.duration == 180

        assert track.artist.mbid == "5436ce22-af50-4714-addc-afd5d2efc77f"
        assert track.artist.name == "Grupo Niche"

    def test__similar_track__none(self) -> None:
        payload: dict[str, Any] = {
            "similartracks": {
                "track": None,
            },
        }

        page = LastFmSimilarTracksResponse.model_validate(payload)
        assert page.similartracks is not None
        assert isinstance(page.similartracks.track, list)
        assert len(page.similartracks.track) == 0

    @pytest.mark.parametrize(
        ("match", "expected_msg"),
        [(-0.01, "Input should be greater than or equal to 0"), (1.01, "Input should be less than or equal to 1")],
    )
    def test__similar_track__track__match(self, match: float, expected_msg: str) -> None:
        payload: dict[str, Any] = {
            "similartracks": {
                "track": {
                    "artist": {
                        "mbid": "5436ce22-af50-4714-addc-afd5d2efc77f",
                        "name": "Grupo Niche",
                    },
                    "match": match,
                    "mbid": "2ced3803-b87a-319f-9926-0388b20608be",
                    "name": "Mi Pueblo",
                },
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            LastFmSimilarTracksResponse.model_validate(payload)

        assert "1 validation error for LastFmSimilarTracksResponse\nsimilartracks.track.0.match" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)
