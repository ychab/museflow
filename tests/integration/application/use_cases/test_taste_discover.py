import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import Reconciler
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter

from tests.integration.factories.models.taste import TasteProfileModelFactory


@pytest.mark.wiremock("gemini", "spotify")
class TestDiscoverTasteUseCase:
    @pytest.fixture
    def use_case(
        self,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
        blacklist_repository: BlacklistRepository,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
        spotify_library: ProviderLibraryPort,
        gemini_advisor: GeminiAdvisorAdapter,
        reconciler: Reconciler,
    ) -> DiscoverTasteUseCase:
        return DiscoverTasteUseCase(
            track_repository=track_repository,
            taste_profile_repository=taste_profile_repository,
            blacklist_repository=blacklist_repository,
            discovery_playlist_repository=discovery_playlist_repository,
            provider_library=spotify_library,
            advisor=gemini_advisor,
            reconciler=reconciler,
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
                playlist_limit=1,
                advisor_limit=5,
                dry_run=False,
            ),
        )

        assert result.provider_playlist is not None
        assert result.provider_playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert result.discovery_playlist is not None
        assert result.discovery_playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert len(result.discovery_playlist.tracks) == len(result.tracks)
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

        assert result.provider_playlist is None
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert result.strategy.search_queries == ["post-rock instrumental", "math rock progressive"]
