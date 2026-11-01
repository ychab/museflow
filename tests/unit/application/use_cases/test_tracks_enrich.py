import logging
from unittest import mock

import pytest

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import EnrichTracksUseCase
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.exceptions import EnricherRateLimitExceeded
from museflow.domain.exceptions import EnricherUnavailableException
from museflow.domain.exceptions import TrackEnrichmentAbortedException
from museflow.domain.exceptions import TrackEnrichmentException
from museflow.domain.value_objects.track import TrackEnrichment

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.track import TrackEnrichmentFactory


class TestEnrichTracksUseCase:
    async def test__no_tracks__returns_zero_counts(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(force=True))

        mock_track_repository.get_list.assert_awaited_once_with(user_id=user.id, missing_fields=None, limit=None)

    async def test__limit__forwarded_to_repository(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(limit=50))

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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(batch_size=2))

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
        mock_enricher.enrich_tracks.side_effect = lambda batch, fields: [
            TrackEnrichmentFactory.build(track_id=t.id) for t in batch
        ]

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(batch_size=2))

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
            RuntimeError("OpenRouter 503"),
            [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks[2:]],
        ]

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(batch_size=2))

        assert result.error_count == 1
        assert result.enriched_count == 2

    @pytest.mark.parametrize(
        ("error", "expected_message", "expected_traceback"),
        [
            pytest.param(
                TrackEnrichmentException("Invalid enrichment response: LLM response truncated (length)"),
                "Enrichment batch 1/2 failed: Invalid enrichment response: LLM response truncated (length)",
                False,
                id="batch_failure",
            ),
            pytest.param(RuntimeError("boom"), "Enrichment batch 1/2 failed", True, id="unexpected"),
        ],
    )
    async def test__enricher_error__logs_traceback_for_unexpected_only(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
        error: Exception,
        expected_message: str,
        expected_traceback: bool,
    ) -> None:
        tracks = TrackFactory.batch(2)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.side_effect = [error, [TrackEnrichmentFactory.build(track_id=tracks[1].id)]]

        with caplog.at_level(logging.WARNING):
            await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(batch_size=1))

        record = next(r for r in caplog.records if r.message == expected_message)
        assert (record.exc_info is not None) is expected_traceback

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(EnricherUnavailableException("Insufficient credits"), id="unavailable"),
            pytest.param(EnricherRateLimitExceeded("Insufficient credits"), id="rate_limit"),
        ],
    )
    async def test__enricher_unavailable__aborts_and_keeps_saved_batches(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
        error: Exception,
    ) -> None:
        tracks = TrackFactory.batch(6)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.side_effect = [
            [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks[:2]],
            error,
        ]

        with pytest.raises(TrackEnrichmentAbortedException, match="Insufficient credits") as exc_info:
            await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput(batch_size=2))

        assert (exc_info.value.batch_index, exc_info.value.total_batches) == (2, 3)
        assert exc_info.value.enriched_count == 2
        assert mock_enricher.enrich_tracks.await_count == 2
        mock_track_repository.bulk_update.assert_awaited_once()

    async def test__consecutive_failures__abort_at_threshold(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(5)
        mock_enricher.enrich_tracks.side_effect = [[], [], TrackEnrichmentException("Flagged"), []]

        with pytest.raises(TrackEnrichmentAbortedException) as exc_info:
            await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
                user, EnrichTracksConfigInput(batch_size=1, max_consecutive_failures=3)
            )

        assert exc_info.value.reason == "3 batches failed in a row (last: Flagged)"
        assert (exc_info.value.batch_index, exc_info.value.total_batches) == (3, 5)
        assert mock_enricher.enrich_tracks.await_count == 3

    @pytest.mark.parametrize(
        ("last_outcome", "expected_last"),
        [
            pytest.param([], "no enrichment returned", id="empty"),
            pytest.param(RuntimeError("boom"), "RuntimeError('boom')", id="unexpected"),
        ],
    )
    async def test__consecutive_failures__reason_names_the_last_failure(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
        last_outcome: list[TrackEnrichment] | Exception,
        expected_last: str,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(2)
        mock_enricher.enrich_tracks.side_effect = [TrackEnrichmentException("Flagged"), last_outcome]

        with pytest.raises(TrackEnrichmentAbortedException) as exc_info:
            await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
                user, EnrichTracksConfigInput(batch_size=1, max_consecutive_failures=2)
            )

        assert exc_info.value.reason == f"2 batches failed in a row (last: {expected_last})"

    async def test__consecutive_failures__reset_by_a_successful_batch(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        tracks = TrackFactory.batch(5)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.side_effect = [
            [],
            TrackEnrichmentException("Flagged"),
            [TrackEnrichmentFactory.build(track_id=tracks[2].id)],
            [],
            [],
        ]

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
            user, EnrichTracksConfigInput(batch_size=1, max_consecutive_failures=3)
        )

        assert result == EnrichTracksReport(enriched_count=1, error_count=4)

    async def test__empty_enricher_result__counted_as_error_not_enriched(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(3)
        mock_enricher.enrich_tracks.return_value = []

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
            user, EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE}))
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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
            user, EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE}))
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

        await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
            user, EnrichTracksConfigInput(fields=frozenset({EnrichField.GENRE}))
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

        result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
            user, EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE}))
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
            result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(user, EnrichTracksConfigInput())

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
            result = await EnrichTracksUseCase(mock_uow, mock_enricher).enrich(
                user, EnrichTracksConfigInput(fields=frozenset({EnrichField.MOOD, EnrichField.LOCALE}))
            )

        assert result == EnrichTracksReport(enriched_count=0, error_count=1)
        mock_track_repository.bulk_update.assert_not_awaited()
        assert "Enrichment returned no moods" in caplog.messages
