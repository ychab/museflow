import pytest

from museflow.application.inputs.enricher import EnrichTracksConfigInput
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.enrichers.gemini.client import GeminiTrackEnricherAdapter

from tests.integration.factories.models.track import TrackModelFactory


@pytest.mark.wiremock("gemini")
class TestTracksEnrichUseCase:
    async def test__nominal(
        self,
        user: User,
        track_repository: TrackRepository,
        gemini_enricher: GeminiTrackEnricherAdapter,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=10),
            track_repository,
            gemini_enricher,
        )

        assert result.enriched_count == 1
        assert result.error_count == 0

        tracks = await track_repository.get_list(user_id=user.id)
        assert len(tracks) == 1
        enriched = tracks[0]
        assert enriched.id == track_db.id
        assert enriched.genres == ["indie folk", "dream pop"]
        assert enriched.moods == ["chill"]

    async def test__unenriched_only__skips_already_enriched(
        self,
        user: User,
        track_repository: TrackRepository,
        gemini_enricher: GeminiTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["hip hop"], moods=["energetic"])
        await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            track_repository,
            gemini_enricher,
        )

        assert result.enriched_count == 1
