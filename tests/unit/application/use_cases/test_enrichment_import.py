from unittest import mock

from museflow.application.inputs.enrich import EnrichEntryInput
from museflow.application.use_cases.enrichment_import import import_enrichment
from museflow.domain.entities.user import User
from museflow.domain.enums import GenreTag


class TestImportEnrichmentUseCase:
    async def test__fingerprint_not_found(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await import_enrichment(
            user_id=user.id,
            entries=[EnrichEntryInput(fingerprint="unknown-fp", genres=[GenreTag.ROCK])],
            uow=mock_uow,
        )

        assert result.imported_count == 0
        assert result.not_found_count == 1
        mock_track_repository.bulk_update.assert_not_awaited()
