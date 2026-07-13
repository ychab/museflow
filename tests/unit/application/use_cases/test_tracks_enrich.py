from unittest import mock

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.factories.value_objects.track import TrackEnrichmentFactory


class TestTracksEnrichUseCase:
    async def test__no_tracks__returns_zero_counts(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = []

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_track_repository,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=0, error_count=0)
        mock_enricher.enrich_tracks.assert_not_awaited()

    async def test__nominal__enriches_all_tracks(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        tracks = TrackFactory.batch(3)
        mock_track_repository.get_list.return_value = tracks
        enrichments = [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks]
        mock_enricher.enrich_tracks.return_value = enrichments

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_track_repository,
            mock_enricher,
        )

        assert result == EnrichTracksReport(enriched_count=3, error_count=0)
        mock_track_repository.bulk_update.assert_awaited_once()
        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset(EnrichField), limit=None
        )

    async def test__force__disables_unenriched_only_filter(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(force=True),
            mock_track_repository,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(user_id=user.id, missing_fields=None, limit=None)

    async def test__limit__forwarded_to_repository(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(limit=50),
            mock_track_repository,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset(EnrichField), limit=50
        )

    async def test__batch_splitting__calls_enricher_once_per_batch(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        tracks = TrackFactory.batch(5)
        mock_track_repository.get_list.return_value = tracks
        mock_enricher.enrich_tracks.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=2),
            mock_track_repository,
            mock_enricher,
        )

        assert mock_enricher.enrich_tracks.await_count == 3  # ceil(5/2) = 3

    async def test__enricher_error__increments_error_count_and_continues(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        tracks = TrackFactory.batch(4)
        mock_track_repository.get_list.return_value = tracks

        mock_enricher.enrich_tracks.side_effect = [
            RuntimeError("Gemini 503"),
            [TrackEnrichmentFactory.build(track_id=t.id) for t in tracks[2:]],
        ]

        result = await tracks_enrich(
            user,
            EnrichTracksConfigInput(batch_size=2),
            mock_track_repository,
            mock_enricher,
        )

        assert result.error_count == 1
        assert result.enriched_count == 2

    async def test__genres__written_directly_to_update(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        track = TrackFactory.build()
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(
                track_id=track.id,
                genres=[GenreTag.HIP_HOP, GenreTag.RAP, GenreTag.AFRO_RAP],
                moods=["chill"],
                locale="fr",
            )
        ]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(),
            mock_track_repository,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset(EnrichField)
        assert len(tracks_arg) == 1
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP, GenreTag.RAP, GenreTag.AFRO_RAP]
        assert tracks_arg[0].locale == "fr"

    async def test__locale_only__only_locale_written_and_existing_genres_preserved(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        track = TrackFactory.build(genres=[GenreTag.HIP_HOP], moods=["chill"])
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [TrackEnrichmentFactory.build(track_id=track.id, locale="fr")]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE})),
            mock_track_repository,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset({EnrichField.LOCALE})
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP]
        assert tracks_arg[0].locale == "fr"

    async def test__locale_only__missing_fields_filter_uses_only_locale(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = []

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.LOCALE})),
            mock_track_repository,
            mock_enricher,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, missing_fields=frozenset({EnrichField.LOCALE}), limit=None
        )

    async def test__genre_only__locale_field_not_written(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_enricher: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        track = TrackFactory.build(locale="en")
        mock_track_repository.get_list.return_value = [track]
        mock_enricher.enrich_tracks.return_value = [
            TrackEnrichmentFactory.build(track_id=track.id, genres=[GenreTag.HIP_HOP])
        ]

        await tracks_enrich(
            user,
            EnrichTracksConfigInput(fields=frozenset({EnrichField.GENRE})),
            mock_track_repository,
            mock_enricher,
        )

        call_args = mock_track_repository.bulk_update.call_args
        tracks_arg = call_args[0][0]
        fields_arg = call_args.kwargs["fields"]
        assert fields_arg == frozenset({EnrichField.GENRE})
        assert tracks_arg[0].genres == [GenreTag.HIP_HOP]
        assert tracks_arg[0].locale == "en"  # unchanged
