import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.use_cases.discover_taste import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter

from tests.integration.factories.models.taste import TasteProfileModelFactory


@pytest.mark.wiremock("gemini")
@pytest.mark.wiremock("spotify")
class TestDiscoverTasteUseCase:
    @pytest.fixture
    def use_case(
        self,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
        spotify_library: ProviderLibraryPort,
        gemini_advisor: GeminiAdvisorAdapter,
        track_reconciler: TrackReconciler,
    ) -> DiscoverTasteUseCase:
        return DiscoverTasteUseCase(
            track_repository=track_repository,
            taste_profile_repository=taste_profile_repository,
            provider_library=spotify_library,
            advisor_agent=gemini_advisor,
            track_reconciler=track_reconciler,
            profiler=TasteProfiler.GEMINI,
        )

    async def test__nominal(
        self,
        use_case: DiscoverTasteUseCase,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, profiler=TasteProfiler.GEMINI.value)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_size=1,
                similar_limit=5,
                dry_run=False,
            ),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
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
                playlist_size=1,
                similar_limit=5,
                dry_run=True,
            ),
        )

        assert result.playlist is None
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert result.strategy.search_queries == ["post-rock instrumental", "math rock progressive"]
