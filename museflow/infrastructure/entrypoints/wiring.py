"""Builds the adapters from the settings, for every entrypoint.

Framework-free: each entrypoint wraps these builders in its own way of providing them (FastAPI `Depends`, the CLI
logic) and supplies what only it knows, such as the units of work of the running request or command.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import AccessTokenManagerPort
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
from museflow.infrastructure.adapters.enrichers.openrouter.client import OpenRouterTrackEnricherAdapter
from museflow.infrastructure.adapters.profilers.openrouter.client import OpenRouterTasteProfileAdapter
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import JwtAccessTokenManager
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.openrouter import openrouter_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings

# --- Security ---


def build_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def build_access_token_manager() -> AccessTokenManagerPort:
    return JwtAccessTokenManager()


def build_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


# --- LLM ---


@asynccontextmanager
async def build_advisor(model: str | None = None, meter: LLMUsageMeter | None = None) -> AsyncGenerator[AdvisorPort]:
    client = _build_openrouter_client(meter)
    llm = openrouter_settings.ADVISOR.with_model(model)

    async with OpenRouterAdvisorAdapter(client=client, llm=llm) as advisor:
        await client.check_models({"advisor": llm})
        yield advisor


@asynccontextmanager
async def build_enricher(
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> AsyncGenerator[TrackEnricherPort]:
    client = _build_openrouter_client(meter)
    llm = openrouter_settings.ENRICHER.with_model(model)

    async with OpenRouterTrackEnricherAdapter(client=client, llm=llm) as enricher:
        await client.check_models({"enricher": llm})
        yield enricher


@asynccontextmanager
async def build_profiler(
    segment_model: str | None = None,
    merge_model: str | None = None,
    reflect_model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> AsyncGenerator[TasteProfilerPort]:
    client = _build_openrouter_client(meter)
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
async def build_provider_oauth(provider: MusicProvider) -> AsyncGenerator[ProviderOAuthPort]:
    match provider:
        case MusicProvider.SPOTIFY:
            async with _build_spotify_oauth() as oauth_client:
                yield oauth_client
        case _:
            raise ValueError(f"Unknown provider: {provider}")


@asynccontextmanager
async def build_provider_library(
    provider: MusicProvider,
    user: User,
    uow: UnitOfWorkPort,
    token_uow: UnitOfWorkPort,
) -> AsyncGenerator[ProviderLibraryPort]:
    """Builds the user's provider library from their stored token: call it outside any `uow` block.

    Args:
        provider: The provider of the library.
        user: The owner of the library.
        uow: Reads the stored token.
        token_uow: Saves a token refreshed during a remote call of the library, so another instance than the one
            of the use case, which may be inside a block at that moment.

    Raises:
        ProviderAuthTokenNotFoundError: If the user never connected the provider.
    """
    auth_token = await get_provider_token(user_id=user.id, provider=provider, uow=uow)

    if auth_token is None:
        raise ProviderAuthTokenNotFoundError(f"No {provider} auth token found.")

    match provider:
        case MusicProvider.SPOTIFY:
            async with _build_spotify_oauth() as oauth_client:
                library_factory = SpotifyLibraryFactory(uow=token_uow, oauth_client=oauth_client)
                yield library_factory.create(user=user, auth_token=auth_token)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def build_streaming_history(provider: MusicProvider) -> StreamingHistoryPort:
    match provider:
        case MusicProvider.SPOTIFY:
            return SpotifyStreamingHistoryAdapter()
        case _:
            raise ValueError(f"Unknown provider: {provider}")


# --- Private helpers ---


def _build_openrouter_client(meter: LLMUsageMeter | None) -> OpenRouterClient:
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
async def _build_spotify_oauth() -> AsyncGenerator[SpotifyOAuthAdapter]:
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
    ) as oauth_client:
        yield oauth_client
