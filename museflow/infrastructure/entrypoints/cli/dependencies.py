from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.enums import MusicAdvisor
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TasteProfiler
from museflow.domain.services.reconciler import Reconciler
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.database.session import async_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.adapters.enrichers.openrouter.client import OpenRouterTrackEnricherAdapter
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.gemini import gemini_settings
from museflow.infrastructure.config.settings.openrouter import openrouter_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings

ADVISOR_TO_PROFILER: dict[MusicAdvisor, TasteProfiler] = {
    MusicAdvisor.GEMINI: TasteProfiler.GEMINI,
}


# --- Security ---


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


# --- LLM ---


def get_openrouter_client() -> OpenRouterClient:
    return OpenRouterClient(
        api_key=openrouter_settings.API_KEY,
        base_url=openrouter_settings.BASE_URL,
        timeout=openrouter_settings.HTTP_TIMEOUT,
        max_retry_wait=openrouter_settings.HTTP_MAX_RETRY_WAIT,
        zdr=openrouter_settings.ZDR,
    )


# --- Context manager ---


@asynccontextmanager
async def get_spotify_oauth() -> AsyncGenerator[SpotifyOAuthAdapter]:
    async with SpotifyOAuthAdapter(
        client_id=spotify_settings.CLIENT_ID,
        client_secret=spotify_settings.CLIENT_SECRET,
        redirect_uri=spotify_settings.REDIRECT_URI,
        base_url=spotify_settings.BASE_URL,
        auth_endpoint=spotify_settings.AUTH_ENDPOINT,
        token_endpoint=spotify_settings.TOKEN_ENDPOINT,
        timeout=spotify_settings.HTTP_TIMEOUT,
        token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
        max_retry_wait=spotify_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


@asynccontextmanager
async def get_gemini_taste_advisor() -> AsyncGenerator[AdvisorPort]:
    async with GeminiAdvisorAdapter(
        api_key=gemini_settings.API_KEY,
        model=gemini_settings.ADVISOR_MODEL,
        base_url=gemini_settings.BASE_URL,
        timeout=gemini_settings.HTTP_TIMEOUT,
        max_retry_wait=gemini_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


@asynccontextmanager
async def get_gemini_profiler() -> AsyncGenerator[TasteProfilerPort]:
    async with GeminiTasteProfileAdapter(
        api_key=gemini_settings.API_KEY,
        segment_model=gemini_settings.PROFILER_SEGMENT_MODEL,
        merge_model=gemini_settings.PROFILER_MERGE_MODEL,
        reflect_model=gemini_settings.PROFILER_REFLECT_MODEL,
        base_url=gemini_settings.BASE_URL,
        timeout=gemini_settings.HTTP_TIMEOUT,
        max_retry_wait=gemini_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


@asynccontextmanager
async def get_enricher(model: str | None = None) -> AsyncGenerator[TrackEnricherPort]:
    client = get_openrouter_client()
    llm = openrouter_settings.ENRICHER.with_model(model)
    async with OpenRouterTrackEnricherAdapter(client=client, llm=llm) as enricher:
        await client.check_models({"enricher": llm})
        yield enricher


@asynccontextmanager
async def get_provider_oauth(provider: MusicProvider) -> AsyncGenerator[SpotifyOAuthAdapter]:
    match provider:
        case MusicProvider.SPOTIFY:
            async with get_spotify_oauth() as client:
                yield client
        case _:
            raise ValueError(f"Unknown provider: {provider}")


@asynccontextmanager
async def get_advisor_adapter(advisor: MusicAdvisor) -> AsyncGenerator[AdvisorPort]:
    match advisor:
        case MusicAdvisor.GEMINI:
            async with get_gemini_taste_advisor() as adapter:
                yield adapter
        case _:
            raise ValueError(f"Unknown advisor: {advisor}")


@asynccontextmanager
async def get_taste_profiler(profiler: TasteProfiler) -> AsyncGenerator[TasteProfilerPort]:
    match profiler:
        case TasteProfiler.GEMINI:
            async with get_gemini_profiler() as adapter:
                yield adapter
        case _:
            raise ValueError(f"Unknown profiler: {profiler}")


# --- Adapter manager ---


def get_spotify_library_factory(spotify_client: SpotifyOAuthAdapter) -> SpotifyLibraryFactory:
    # Its own unit of work: a token refresh happens in the middle of a remote call of the use case.
    return SpotifyLibraryFactory(uow=get_unit_of_work(), oauth_client=spotify_client)


def get_provider_library_factory(provider: MusicProvider, oauth_client: SpotifyOAuthAdapter) -> SpotifyLibraryFactory:
    match provider:
        case MusicProvider.SPOTIFY:
            return get_spotify_library_factory(spotify_client=oauth_client)
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
    return SQLUnitOfWork(async_session_factory)


# --- Services ---


def get_reconciler() -> Reconciler:
    return Reconciler(match_threshold=app_settings.RECONCILER_MATCH_THRESHOLD)
