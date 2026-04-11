from typing import Any

import pytest

from museflow.application.inputs.discovery import DiscoverySimilarConfigInput
from museflow.application.ports.advisors.similar import AdvisorSimilarPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.use_cases.discover_similar import DiscoverSimilarUseCase
from museflow.domain.entities.music import Track
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import TrackReconciler

from tests.integration.factories.models.music import TrackModelFactory
from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("lastfm")
class TestDiscoverSimilarSpotifyLastFMUseCase:
    @pytest.fixture
    def use_case(
        self,
        track_repository: TrackRepository,
        spotify_library: ProviderLibraryPort,
        lastfm_advisor: AdvisorSimilarPort,
        track_reconciler: TrackReconciler,
    ) -> DiscoverSimilarUseCase:
        return DiscoverSimilarUseCase(
            track_repository=track_repository,
            provider_library=spotify_library,
            advisor_client=lastfm_advisor,
            track_reconciler=track_reconciler,
        )

    @pytest.fixture
    async def track_seed(self, user: User) -> Track:
        track_seed_db = await TrackModelFactory.create_async(
            name="La Negra No Quiere",
            artists=[
                {
                    "name": "Grupo Niche",
                    "provider_id": "1zng9JZpblpk48IPceRWs8",
                }
            ],
            user_id=user.id,
        )
        return track_seed_db.to_entity()

    @pytest.fixture
    def wiremock_lastfm_response(self) -> dict[str, Any]:
        return {
            "similartracks": {
                "track": [
                    {
                        "artist": {
                            "mbid": "5436ce22-af50-4714-addc-afd5d2efc77f",
                            "name": "Grupo Niche",
                        },
                        "match": 1.0,
                        "mbid": "2ced3803-b87a-319f-9926-0388b20608be",
                        "name": "Mi Pueblo",
                    }
                ]
            }
        }

    async def test_execute__nominal(
        self,
        use_case: DiscoverSimilarUseCase,
        user: User,
        track_seed: Track,
        wiremock_lastfm_response: dict[str, Any],
        track_repository: TrackRepository,
        lastfm_wiremock: WireMockContext,
    ) -> None:
        lastfm_wiremock.create_mapping(
            method="GET",
            url_path="/",
            status=200,
            query_params={"method": "track.getSimilar"},
            json_body=wiremock_lastfm_response,
        )

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverySimilarConfigInput(
                seed_limit=5,
                playlist_size=1,
                max_attempts=1,
            ),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert len(result.playlist.tracks) == 1

        track = result.playlist.tracks[0]
        assert track.provider_id == "1B7EbqtFdlKqLSBXrKKfW8"
        assert track.name == "Mi Pueblo"
        assert len(track.artists) == 1
        assert track.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert track.artists[0].name == "Grupo Niche"

        assert len(result.reports) == 1
        assert result.reports[0].tracks_new >= 1


@pytest.mark.wiremock("spotify")
class TestDiscoverSimilarSpotifyGeminiUseCase:
    @pytest.fixture
    def use_case(
        self,
        track_repository: TrackRepository,
        spotify_library: ProviderLibraryPort,
        gemini_advisor: AdvisorSimilarPort,
        track_reconciler: TrackReconciler,
    ) -> DiscoverSimilarUseCase:
        return DiscoverSimilarUseCase(
            track_repository=track_repository,
            provider_library=spotify_library,
            advisor_client=gemini_advisor,
            track_reconciler=track_reconciler,
        )

    @pytest.fixture
    async def track_seed(self, user: User) -> Track:
        track_seed_db = await TrackModelFactory.create_async(
            name="La Negra No Quiere",
            artists=[{"name": "Grupo Niche", "provider_id": "1zng9JZpblpk48IPceRWs8"}],
            user_id=user.id,
        )
        return track_seed_db.to_entity()

    async def test_execute__nominal(
        self,
        use_case: DiscoverSimilarUseCase,
        user: User,
        track_seed: Track,
        track_repository: TrackRepository,
    ) -> None:
        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverySimilarConfigInput(
                seed_limit=5,
                playlist_size=1,
                max_attempts=1,
            ),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert len(result.playlist.tracks) == 1

        track = result.playlist.tracks[0]
        assert track.provider_id == "1B7EbqtFdlKqLSBXrKKfW8"
        assert track.name == "Mi Pueblo"
        assert len(track.artists) == 1
        assert track.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert track.artists[0].name == "Grupo Niche"

        assert len(result.reports) == 1
        assert result.reports[0].tracks_new >= 1
