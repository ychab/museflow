import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import TasteProfiler
from museflow.domain.services.reconciler import Reconciler
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter

from tests.integration.factories.models.taste import TasteProfileModelFactory


@pytest.mark.wiremock("gemini", "spotify")
class TestDiscoverTasteUseCase:
    @pytest.fixture
    def use_case(
        self,
        uow: UnitOfWorkPort,
        spotify_library: ProviderLibraryPort,
        gemini_advisor: GeminiAdvisorAdapter,
        reconciler: Reconciler,
    ) -> DiscoverTasteUseCase:
        return DiscoverTasteUseCase(
            uow=uow,
            provider_library=spotify_library,
            advisor=gemini_advisor,
            reconciler=reconciler,
            profiler=TasteProfiler.GEMINI,
        )

    async def test__nominal(
        self,
        use_case: DiscoverTasteUseCase,
        user: User,
    ) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, profiler=TasteProfiler.GEMINI.value)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                advisor_limit=5,
                dry_run=False,
            ),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert len(result.playlist.tracks) == len(result.tracks)
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert result.strategy.search_queries == ["post-rock instrumental", "math rock progressive"]
        assert len(result.tracks) >= 1

    async def test__dry_run(
        self,
        use_case: DiscoverTasteUseCase,
        user: User,
    ) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, profiler=TasteProfiler.GEMINI.value)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                advisor_limit=5,
                dry_run=True,
            ),
        )

        assert result.playlist is None
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert result.strategy.search_queries == ["post-rock instrumental", "math rock progressive"]
