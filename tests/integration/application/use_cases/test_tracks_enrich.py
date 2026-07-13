import pytest

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
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
        assert enriched.genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        assert enriched.moods == ["chill"]

    async def test__unenriched_only__skips_already_enriched(
        self,
        user: User,
        track_repository: TrackRepository,
        gemini_enricher: GeminiTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["hip-hop"], moods=["energetic"], locale="en")
        await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            track_repository,
            gemini_enricher,
        )

        assert result.enriched_count == 1

    async def test__locale_only__preserves_existing_genres_and_updates_locale(
        self,
        user: User,
        track_repository: TrackRepository,
        gemini_enricher: GeminiTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["hip-hop"], moods=["energetic"])

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=10, fields=frozenset({EnrichField.LOCALE})),
            track_repository,
            gemini_enricher,
        )

        assert result.enriched_count == 1
        tracks = await track_repository.get_list(user_id=user.id)
        assert tracks[0].genres == [GenreTag.HIP_HOP]
        assert tracks[0].locale == "fr"

    async def test__genre_only__updates_genres_and_leaves_locale_null(
        self,
        user: User,
        track_repository: TrackRepository,
        gemini_enricher: GeminiTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id)

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=10, fields=frozenset({EnrichField.GENRE})),
            track_repository,
            gemini_enricher,
        )

        assert result.enriched_count == 1
        tracks = await track_repository.get_list(user_id=user.id)
        assert tracks[0].genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        assert tracks[0].locale is None
