from typing import Any

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
