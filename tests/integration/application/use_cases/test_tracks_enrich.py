from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.tracks_enrich import EnrichTracksUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import LLMOperation
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.enrichers.openrouter.client import OpenRouterTrackEnricherAdapter

from tests.integration.factories.models.track import TrackModelFactory


@pytest.mark.wiremock("openrouter")
class TestEnrichTracksUseCase:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        uow: UnitOfWorkPort,
        user: User,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)

        result = await EnrichTracksUseCase(uow, openrouter_enricher).enrich(
            user,
            EnrichTracksConfigInput(batch_size=10),
        )

        assert result.enriched_count == 1
        assert result.error_count == 0

        async with uow:
            tracks = await uow.tracks.get_list(user_id=user.id)
        assert len(tracks) == 1
        enriched = tracks[0]
        assert enriched.id == track_db.id
        assert enriched.genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        assert enriched.moods == ["chill"]

        row = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalar_one()
        assert (row.operation, row.step, row.calls) == (LLMOperation.ENRICH, "enricher", 1)

    async def test__fingerprints__only_those_tracks(
        self,
        uow: UnitOfWorkPort,
        user: User,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
    ) -> None:
        sample_db = await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])
        other_db = await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])

        result = await EnrichTracksUseCase(uow, openrouter_enricher).enrich(
            user,
            EnrichTracksConfigInput(fingerprints=[sample_db.fingerprint, "unknown"]),
        )

        assert (result.enriched_count, result.not_found_count) == (1, 1)
        async with uow:
            tracks = {track.id: track for track in await uow.tracks.get_list(user_id=user.id)}
        assert tracks[sample_db.id].genres
        assert tracks[other_db.id].genres == []

    async def test__unenriched_only__skips_already_enriched(
        self,
        uow: UnitOfWorkPort,
        user: User,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["hip-hop"], moods=["energetic"], locales=["en"])
        await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])

        result = await EnrichTracksUseCase(uow, openrouter_enricher).enrich(
            user,
            EnrichTracksConfigInput(),
        )

        assert result.enriched_count == 1

    async def test__locales_only__preserves_existing_genres_and_updates_locales(
        self,
        uow: UnitOfWorkPort,
        user: User,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, genres=["hip-hop"], moods=["energetic"])

        result = await EnrichTracksUseCase(uow, openrouter_enricher).enrich(
            user,
            EnrichTracksConfigInput(batch_size=10, fields=frozenset({EnrichField.LOCALE})),
        )

        assert result.enriched_count == 1
        async with uow:
            tracks = await uow.tracks.get_list(user_id=user.id)
        assert tracks[0].genres == [GenreTag.HIP_HOP]
        assert tracks[0].locales == ["fr"]

    async def test__genre_only__updates_genres_and_leaves_locales_null(
        self,
        uow: UnitOfWorkPort,
        user: User,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id)

        result = await EnrichTracksUseCase(uow, openrouter_enricher).enrich(
            user,
            EnrichTracksConfigInput(batch_size=10, fields=frozenset({EnrichField.GENRE})),
        )

        assert result.enriched_count == 1
        async with uow:
            tracks = await uow.tracks.get_list(user_id=user.id)
        assert tracks[0].genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        assert tracks[0].locales is None
