from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.enrich.tracks import enrich_tracks_logic


@pytest.mark.wiremock("openrouter")
@pytest.mark.usefixtures("openrouter_settings_wiremock")
class TestEnrichTracksLogic:
    """Tests only the CLI logic's own behavior: user lookup + delegation to the use case."""

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.enrich.tracks.EnrichTracksUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value.enrich.return_value = EnrichTracksReport(enriched_count=1, error_count=0)
            yield patched.return_value

    async def test__nominal(self, user: User, mock_use_case: mock.Mock) -> None:
        result = await enrich_tracks_logic(email=user.email, model="google/gemini-3.5-flash")

        assert result.enriched_count == 1
        called_user = mock_use_case.enrich.call_args.kwargs["user"]
        assert called_user.id == user.id
