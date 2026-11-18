import asyncio
from collections.abc import AsyncGenerator
from collections.abc import Coroutine
from collections.abc import Iterator
from contextlib import asynccontextmanager
from contextlib import contextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
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
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.openrouter import openrouter_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings

# The database of the running command, open between the start and the end of `init_logic_runner`.
session_factory: async_sessionmaker[AsyncSession] | None = None


# --- Event loop ---


def run_logic[T](main: Coroutine[Any, Any, T]) -> T:
    """Runs a command's logic like `asyncio.run`, with the database open for the run."""
    with init_logic_runner() as runner:
        result = runner.run(main)
    return result


@contextmanager
def init_logic_runner() -> Iterator[asyncio.Runner]:
    """An `asyncio.Runner` with the database open, for a command that prints between two steps of its logic.

    The engine is created in the runner's event loop, which its pooled connections are bound to, and disposed of in
    that loop when the command ends: a second loop could not reuse them.
    """
    global session_factory

    with asyncio.Runner() as runner:
        engine = create_engine_from_settings()
        session_factory = create_session_factory(engine)
        try:
            yield runner
        finally:
            session_factory = None
            runner.run(engine.dispose())


# --- Security ---


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


# --- LLM ---


def get_openrouter_client(meter: LLMUsageMeter | None = None) -> OpenRouterClient:
    return OpenRouterClient(
        api_key=openrouter_settings.API_KEY.get_secret_value(),
        base_url=openrouter_settings.BASE_URL,
        verify_ssl=openrouter_settings.VERIFY_SSL,
        timeout=openrouter_settings.HTTP_TIMEOUT,
        max_retry_wait=openrouter_settings.HTTP_MAX_RETRY_WAIT,
        zdr=openrouter_settings.ZDR,
        meter=meter,
    )


# --- Context manager ---


@asynccontextmanager
async def get_advisor(model: str | None = None, meter: LLMUsageMeter | None = None) -> AsyncGenerator[AdvisorPort]:
    client = get_openrouter_client(meter)
    llm = openrouter_settings.ADVISOR.with_model(model)

    async with OpenRouterAdvisorAdapter(client=client, llm=llm) as advisor:
        await client.check_models({"advisor": llm})
        yield advisor


@asynccontextmanager
async def get_enricher(
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> AsyncGenerator[TrackEnricherPort]:
    client = get_openrouter_client(meter)
    llm = openrouter_settings.ENRICHER.with_model(model)

    async with OpenRouterTrackEnricherAdapter(client=client, llm=llm) as enricher:
        await client.check_models({"enricher": llm})
        yield enricher


@asynccontextmanager
async def get_profiler(
    segment_model: str | None = None,
    merge_model: str | None = None,
    reflect_model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> AsyncGenerator[TasteProfilerPort]:
    client = get_openrouter_client(meter)
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


@asynccontextmanager
async def get_provider_oauth(provider: MusicProvider) -> AsyncGenerator[ProviderOAuthPort]:
    match provider:
        case MusicProvider.SPOTIFY:
            async with get_spotify_oauth() as client:
                yield client
        case _:
            raise ValueError(f"Unknown provider: {provider}")


@asynccontextmanager
async def get_spotify_oauth() -> AsyncGenerator[SpotifyOAuthAdapter]:
    async with SpotifyOAuthAdapter(
        client_id=spotify_settings.CLIENT_ID,
        client_secret=spotify_settings.CLIENT_SECRET.get_secret_value(),
        redirect_uri=spotify_settings.REDIRECT_URI,
        base_url=spotify_settings.BASE_URL,
        auth_endpoint=spotify_settings.AUTH_ENDPOINT,
        token_endpoint=spotify_settings.TOKEN_ENDPOINT,
        timeout=spotify_settings.HTTP_TIMEOUT,
        token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
        max_retry_wait=spotify_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


# --- Adapter manager ---


def get_spotify_library_factory(spotify_client: SpotifyOAuthAdapter) -> SpotifyLibraryFactory:
    # Its own unit of work: a token refresh happens in the middle of a remote call of the use case.
    return SpotifyLibraryFactory(uow=get_unit_of_work(), oauth_client=spotify_client)


@asynccontextmanager
async def get_provider_library(
    provider: MusicProvider,
    user: User,
    uow: UnitOfWorkPort,
) -> AsyncGenerator[ProviderLibraryPort]:
    """Builds the user's provider library from their stored token: call it outside any `uow` block.

    Raises:
        ProviderAuthTokenNotFoundError: If the user never connected the provider.
    """
    auth_token = await get_provider_token(user_id=user.id, provider=provider, uow=uow)

    if auth_token is None:
        raise ProviderAuthTokenNotFoundError(
            f"No {provider} auth token found — run 'museflow provider connect --provider {provider}' first."
        )

    match provider:
        case MusicProvider.SPOTIFY:
            async with get_spotify_oauth() as oauth_client:
                yield get_spotify_library_factory(spotify_client=oauth_client).create(user=user, auth_token=auth_token)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_streaming_history_adapter(provider: MusicProvider) -> StreamingHistoryPort:
    match provider:
        case MusicProvider.SPOTIFY:
            return SpotifyStreamingHistoryAdapter()
        case _:
            raise ValueError(f"Unknown provider: {provider}")


# --- Unit of work ---


def get_unit_of_work() -> UnitOfWorkPort:
    """The unit of work of the running command.

    Raises:
        RuntimeError: If the command runs its logic without `run_logic` or `init_logic_runner`.
    """
    if session_factory is None:
        raise RuntimeError("No database open: run the command logic through run_logic()")
    return SQLUnitOfWork(session_factory)
