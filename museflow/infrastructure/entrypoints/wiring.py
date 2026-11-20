from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Self

from pydantic import AnyUrl

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.storage import FileStoragePort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_token_get import get_provider_token
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.database.session import create_engine_from_settings
from museflow.infrastructure.adapters.database.session import create_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.adapters.enrichers.openrouter.client import OpenRouterTrackEnricherAdapter
from museflow.infrastructure.adapters.profilers.openrouter.client import OpenRouterTasteProfileAdapter
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import JwtAccessTokenManager
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.adapters.storage.local import LocalFileStorage
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.openrouter import openrouter_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings


class Wiring:
    """Builds the adapters of one process, for every entrypoint, from the settings and the resources it holds.

    The composition root of the process: it holds the process resources and builds the adapters (what other stacks
    call a DI container). Framework-free: an entrypoint opens one per process (`open`) and hands it to its own code, the CLI logic or the
    FastAPI dependencies. Each `build_*` returns a new instance the caller owns: an async context manager when the
    adapter holds a client to close.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @classmethod
    @asynccontextmanager
    async def open(cls) -> AsyncGenerator[Self]:
        """The wiring of the running process.

        Its resources are created in the running event loop, which their pooled connections are bound to, and closed
        on exit.
        """
        engine = create_engine_from_settings()
        try:
            yield cls(create_session_factory(engine))
        finally:
            await engine.dispose()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """The raw sessions, for what the unit of work does not cover (the API health check)."""
        return self._session_factory

    # --- Database ---

    def build_unit_of_work(self) -> UnitOfWorkPort:
        return SQLUnitOfWork(self._session_factory)

    # --- Security ---

    def build_password_hasher(self) -> PasswordHasherPort:
        return Argon2PasswordHasher()

    def build_access_token_manager(self) -> AccessTokenManagerPort:
        return JwtAccessTokenManager()

    def build_state_token_generator(self) -> StateTokenGeneratorPort:
        return SystemStateTokenGenerator()

    # --- Files ---

    def build_file_storage(self) -> FileStoragePort:
        return LocalFileStorage(root=app_settings.FILE_STORAGE_DIR)

    # --- LLM ---

    @asynccontextmanager
    async def build_advisor(
        self,
        model: str | None = None,
        meter: LLMUsageMeter | None = None,
    ) -> AsyncGenerator[AdvisorPort]:
        client = self._build_openrouter_client(meter)
        llm = openrouter_settings.ADVISOR.with_model(model)

        async with OpenRouterAdvisorAdapter(client=client, llm=llm) as advisor:
            await client.check_models({"advisor": llm})
            yield advisor

    @asynccontextmanager
    async def build_enricher(
        self,
        model: str | None = None,
        meter: LLMUsageMeter | None = None,
    ) -> AsyncGenerator[TrackEnricherPort]:
        client = self._build_openrouter_client(meter)
        llm = openrouter_settings.ENRICHER.with_model(model)

        async with OpenRouterTrackEnricherAdapter(client=client, llm=llm) as enricher:
            await client.check_models({"enricher": llm})
            yield enricher

    @asynccontextmanager
    async def build_profiler(
        self,
        segment_model: str | None = None,
        merge_model: str | None = None,
        reflect_model: str | None = None,
        meter: LLMUsageMeter | None = None,
    ) -> AsyncGenerator[TasteProfilerPort]:
        client = self._build_openrouter_client(meter)
        segment_llm = openrouter_settings.PROFILER_SEGMENT.with_model(segment_model)
        merge_llm = openrouter_settings.PROFILER_MERGE.with_model(merge_model)
        reflect_llm = openrouter_settings.PROFILER_REFLECT.with_model(reflect_model)

        async with OpenRouterTasteProfileAdapter(
            client=client,
            segment_llm=segment_llm,
            merge_llm=merge_llm,
            reflect_llm=reflect_llm,
        ) as profiler:
            await client.check_models(
                {"profiler segment": segment_llm, "profiler merge": merge_llm, "profiler reflect": reflect_llm}
            )
            yield profiler

    # --- Providers ---

    @asynccontextmanager
    async def build_provider_oauth(
        self,
        provider: MusicProvider,
        redirect_uri: AnyUrl | None = None,
    ) -> AsyncGenerator[ProviderOAuthPort]:
        """The OAuth adapter of a provider: `redirect_uri`, where the provider sends the browser back, starts or ends a
        flow; without it, the adapter only refreshes tokens."""
        match provider:
            case MusicProvider.SPOTIFY:
                async with self._build_spotify_oauth(redirect_uri) as oauth_client:
                    yield oauth_client
            case _:
                raise ValueError(f"Unknown provider: {provider}")

    @asynccontextmanager
    async def build_provider_library(
        self,
        provider: MusicProvider,
        user: User,
        uow: UnitOfWorkPort,
    ) -> AsyncGenerator[ProviderLibraryPort]:
        """Builds the user's provider library from their stored token: call it outside any `uow` block.

        A token refreshed during a remote call of the library is saved through a unit of work of its own, not the
        one of the use case, which may be inside a block at that moment.

        Raises:
            ProviderAuthTokenNotFoundError: If the user never connected the provider.
        """
        auth_token = await get_provider_token(user_id=user.id, provider=provider, uow=uow)

        if auth_token is None:
            raise ProviderAuthTokenNotFoundError(f"No {provider} auth token found.")

        match provider:
            case MusicProvider.SPOTIFY:
                async with self._build_spotify_oauth() as oauth_client:
                    library_factory = SpotifyLibraryFactory(uow=self.build_unit_of_work(), oauth_client=oauth_client)
                    yield library_factory.create(user=user, auth_token=auth_token)
            case _:
                raise ValueError(f"Unknown provider: {provider}")

    def build_streaming_history(self, provider: MusicProvider) -> StreamingHistoryPort:
        match provider:
            case MusicProvider.SPOTIFY:
                return SpotifyStreamingHistoryAdapter()
            case _:
                raise ValueError(f"Unknown provider: {provider}")

    # --- Private helpers ---

    def _build_openrouter_client(self, meter: LLMUsageMeter | None) -> OpenRouterClient:
        return OpenRouterClient(
            api_key=openrouter_settings.API_KEY.get_secret_value(),
            base_url=openrouter_settings.BASE_URL,
            verify_ssl=openrouter_settings.VERIFY_SSL,
            timeout=openrouter_settings.HTTP_TIMEOUT,
            max_retry_wait=openrouter_settings.HTTP_MAX_RETRY_WAIT,
            zdr=openrouter_settings.ZDR,
            meter=meter,
        )

    @asynccontextmanager
    async def _build_spotify_oauth(self, redirect_uri: AnyUrl | None = None) -> AsyncGenerator[SpotifyOAuthAdapter]:
        async with SpotifyOAuthAdapter(
            client_id=spotify_settings.CLIENT_ID,
            client_secret=spotify_settings.CLIENT_SECRET.get_secret_value(),
            redirect_uri=redirect_uri,
            base_url=spotify_settings.BASE_URL,
            auth_endpoint=spotify_settings.AUTH_ENDPOINT,
            token_endpoint=spotify_settings.TOKEN_ENDPOINT,
            timeout=spotify_settings.HTTP_TIMEOUT,
            token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
            max_retry_wait=spotify_settings.HTTP_MAX_RETRY_WAIT,
        ) as oauth_client:
            yield oauth_client
