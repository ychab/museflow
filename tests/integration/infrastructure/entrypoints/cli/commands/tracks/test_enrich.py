from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.tracks.enrich import enrich_logic


class TestEnrichLogic:
    """Tests only the CLI logic's own behavior: user lookup + delegation to the use case."""

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.tracks.enrich.tracks_enrich"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = EnrichTracksReport(enriched_count=1, error_count=0)
            yield patched

    async def test__nominal(self, user: User, mock_use_case: mock.AsyncMock) -> None:
        result = await enrich_logic(email=user.email)  # type: ignore[arg-type]

        assert result.enriched_count == 1
        called_user = mock_use_case.call_args.args[0]
        assert called_user.id == user.id

    async def test__user_not_found(self, mock_use_case: mock.AsyncMock) -> None:
        with pytest.raises(UserNotFound):
            await enrich_logic(email="nobody@example.com")  # type: ignore[arg-type]
