import logging
from unittest import mock

import pytest

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.value_objects.track import TrackEnrichment

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.track import TrackEnrichmentFactory


class TestTracksEnrichUseCase:
    async def test__no_tracks__returns_zero_counts(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_uow,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=0, error_count=0)
        mock_enricher.enrich_tracks.assert_not_awaited()

    async def test__nominal__enriches_all_tracks(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(3)
        mock_track_repository.get_list.return_value = tracks
        enrichments = [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks]
        mock_enricher.enrich_tracks.return_value = enrichments

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_uow,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=3, error_count=0)
        mock_track_repository.bulk_update.assert_awaited_once()
        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset(EnrichField), limit=None
        )

    async def test__force__disables_unenriched_only_filter(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(force=True),
            mock_uow,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(user_id=user.id, missing_fields=None, limit=None)

    async def test__limit__forwarded_to_repository(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(limit=50),
            mock_uow,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset(EnrichField), limit=50
        )

    async def test__enricher_call__runs_outside_any_block(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(4)
        blocks_open: list[bool] = []

        async def enrich_tracks(batch: list[Track], fields: frozenset[EnrichField]) -> list[TrackEnrichment]:
            blocks_open.append(mock_uow.block_open)
            return [TrackEnrichmentFactory.build(track_id=t.id) for t in batch]

        mock_enricher.enrich_tracks.side_effect = enrich_tracks

        await tracks_enrich(user, EnrichTracksConfigInput(batch_size=2), mock_uow, mock_enricher)

        assert blocks_open == [False, False]
        # The read block, then one write block per batch, so each paid batch is saved on its own
        assert mock_uow.__aenter__.await_count == 3

    async def test__batch_splitting__calls_enricher_once_per_batch(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(5)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=2),
            mock_uow,
            mock_enricher,
        )

        assert mock_enricher.enrich_tracks.await_count == 3  # ceil(5/2) = 3

    async def test__enricher_error__increments_error_count_and_continues(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(4)
        mock_track_repository.get_list.return_value = tracks

        mock_enricher.enrich_tracks.side_effect = [
            RuntimeError("Gemini 503"),
            [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks[2:]],
        ]

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=2),
            mock_uow,
            mock_enricher,
        )

        assert result.error_count == 1
        assert result.enriched_count == 2

    async def test__empty_enricher_result__counted_as_error_not_enriched(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(3)
        mock_enricher.enrich_tracks.return_value = []

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_uow,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=0, error_count=1)
        mock_track_repository.bulk_update.assert_not_awaited()

    async def test__partial_enricher_result__counts_only_returned_tracks(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(3)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.return_value = [TrackEnrichmentFactory.build(track_id=tracks[0].id)]

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_uow,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=1, error_count=0)
        mock_track_repository.bulk_update.assert_awaited_once()

    async def test__genres__written_directly_to_update(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build()
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(
                track_id=track.id,
                genres=[GenreTag.HIP_HOP, GenreTag.RAP, GenreTag.AFRO_RAP],
                moods=["chill"],
                locales=["fr"],
            )
        ]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_uow,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset(EnrichField)
        assert len(tracks_arg) == 1
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP, GenreTag.RAP, GenreTag.AFRO_RAP]
        assert tracks_arg[0].locales == ["fr"]

    async def test__locales_only__only_locales_written_and_existing_genres_preserved(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(genres=[GenreTag.HIP_HOP], moods=["chill"])
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [TrackEnrichmentFactory.build(track_id=track.id, locales=["fr"])]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE})),
            mock_uow,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset({EnrichField.LOCALE})
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP]
        assert tracks_arg[0].locales == ["fr"]

    async def test__locales_only__missing_fields_filter_uses_only_locales(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE})),
            mock_uow,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset({EnrichField.LOCALE}), limit=None
        )

    async def test__genre_only__locales_field_not_written(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(locales=["en"])
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(track_id=track.id, genres=[GenreTag.HIP_HOP])
        ]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.GENRE})),
            mock_uow,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset({EnrichField.GENRE})
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP]
        assert tracks_arg[0].locales == ["en"]  # unchanged

    async def test__empty_locales__written_and_counted(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(locales=None)
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [TrackEnrichmentFactory.build(track_id=track.id, locales=[])]

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE})),
            mock_uow,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=1, error_count=0)
        tracks_arg = mock_track_repository.bulk_update.call_args[0][0]
        assert tracks_arg[0].locales == []

    async def test__empty_genres__not_applied_but_other_fields_are(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track = TrackFactory.build(genres=[GenreTag.HIP_HOP])
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(track_id=track.id, genres=[], moods=[MoodTag.CHILL], locales=["fr"])
        ]

        with caplog.at_level(logging.WARNING):
            result = await tracks_enrich(
                user,
                EnrichTracksConfigInput(),
                mock_uow,
                mock_enricher,
            )

        assert result == EnrichTracksReport(enriched_count=1, error_count=0)
        tracks_arg = mock_track_repository.bulk_update.call_args[0][0]
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP]
        assert tracks_arg[0].moods == [MoodTag.CHILL]
        assert tracks_arg[0].locales == ["fr"]
        assert "Enrichment returned no genres" in caplog.messages

    async def test__empty_moods_and_missing_locales__nothing_applied_and_not_counted(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track = TrackFactory.build()
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(track_id=track.id, moods=[], locales=None)
        ]

        with caplog.at_level(logging.WARNING):
            result = await tracks_enrich(
                user,
                EnrichTracksConfigInput(fields=frozenset({EnrichField.MOOD, EnrichField.LOCALE})),
                mock_uow,
                mock_enricher,
            )

        assert result == EnrichTracksReport(enriched_count=0, error_count=1)
        mock_track_repository.bulk_update.assert_not_awaited()
        assert "Enrichment returned no moods" in caplog.messages
