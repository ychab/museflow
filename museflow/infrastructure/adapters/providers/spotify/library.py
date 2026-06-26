import itertools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from museflow import __project_name__
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPageValidationError
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.types import PlaylistType
from museflow.infrastructure.adapters.providers.spotify.exceptions import SpotifyApiError
from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_playlist
from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_track
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.providers.spotify.queries import SpotifySearchTrackQuery
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyPage
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyPlaylist
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyTrack
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient
from museflow.infrastructure.adapters.providers.spotify.types import SPOTIFY_PLAYLIST_ITEMS_LIMIT
from museflow.infrastructure.adapters.providers.spotify.types import LocalUnsupported

logger = logging.getLogger(__name__)


@dataclass
class SpotifyLibraryFactory:
    """Factory responsible for creating `SpotifyLibraryAdapter` instances.

    This factory handles the dependency injection required to create a
    `SpotifyLibraryAdapter`, specifically wiring up the `SpotifyOAuthSessionClient`
    with the necessary repositories and clients.
    """

    auth_token_repository: OAuthProviderTokenRepository
    oauth_client: SpotifyOAuthAdapter

    def create(self, user: User, auth_token: OAuthProviderUserToken) -> ProviderLibraryPort:
        """Creates a new `SpotifyLibraryAdapter` for a specific user.

        Args:
            user: The user for whom the adapter is being created.
            auth_token: The user's OAuth token.

        Returns:
            A configured `ProviderLibraryPort` implementation for Spotify.
        """
        return SpotifyLibraryAdapter(
            user=user,
            session_client=SpotifyOAuthSessionClient(
                user=user,
                auth_token=auth_token,
                auth_token_repository=self.auth_token_repository,
                oauth_client=self.oauth_client,
            ),
        )


class SpotifyLibraryAdapter(ProviderLibraryPort):
    """Adapter for interacting with the Spotify Web API.

    Implements `ProviderLibraryPort` for track search and playlist creation.
    """

    def __init__(
        self,
        user: User,
        session_client: SpotifyOAuthSessionClient,
    ) -> None:
        self.user = user
        self.session_client = session_client

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def search_tracks(
        self,
        track: str,
        artists: list[str] | None = None,
        is_new: bool = False,
        is_underground: bool = False,
        page_size: int = 10,
        max_pages: int | None = None,
        log_enabled: bool = True,
    ) -> list[Track]:
        query_builder = SpotifySearchTrackQuery(
            track=track,
            artists=artists or [],
            is_new=is_new,
            is_underground=is_underground,
        )

        return await self._fetch_pages(
            endpoint="/search",
            page_model=SpotifyPage[SpotifyTrack],
            page_processor=self._extract_search_tracks,
            page_size=page_size,
            max_pages=max_pages,
            log_enabled=log_enabled,
            log_prefix=f"[Search track {track}]",
            params={
                "q": query_builder.get_query(),
                "type": "track",
            },
            response_key="tracks",
        )

    async def create_playlist(
        self,
        name: str,
        type: PlaylistType,
        tracks: list[Track],
        is_public: bool = False,
    ) -> Playlist:
        # First, create the playlist
        data = await self._execute_request(
            method="POST",
            endpoint="/me/playlists",
            json_data={
                "name": name,
                "public": is_public,
                "collaborative": False,
                "description": f"Auto-generated by {__project_name__}",
            },
        )
        spotify_playlist = SpotifyPlaylist.model_validate(data)

        # Then, insert the playlist tracks in batches (Spotify caps this endpoint at 100 URIs per call).
        all_uris = [f"spotify:track:{track.provider_id}" for track in tracks]
        for batch in itertools.batched(all_uris, SPOTIFY_PLAYLIST_ITEMS_LIMIT, strict=False):
            data = await self._execute_request(
                method="POST",
                endpoint=f"/playlists/{spotify_playlist.id}/items",
                json_data={"uris": list(batch)},
            )
        spotify_playlist.snapshot_id = data["snapshot_id"]

        return to_domain_playlist(spotify_playlist, user_id=self.user.id, type=type, tracks=tracks)

    async def play_track(self, track_provider_id: str) -> None:
        try:
            await self._execute_request(
                method="PUT",
                endpoint="/me/player/play",
                json_data={"uris": [f"spotify:track:{track_provider_id}"]},
                ignored_status_codes=frozenset({404, 403}),
            )
        except SpotifyApiError as e:
            if e.status_code == 404:
                raise ProviderNoActiveDeviceException() from e
            if e.status_code == 403:
                raise ProviderPremiumRequiredException() from e
            raise  # pragma: no cover

    # -------------------------------------------------------------------------
    # Core Logic
    # -------------------------------------------------------------------------

    async def _fetch_pages(
        self,
        endpoint: str,
        page_model: type[SpotifyPage[SpotifyTrack]],
        page_processor: Callable[[SpotifyPage[SpotifyTrack], int], list[Track]],
        method: str = "GET",
        params: dict[str, Any] | None = None,
        offset: int = 0,
        page_size: int = 50,
        max_pages: int | None = None,
        log_enabled: bool = True,
        log_prefix: str = "",
        response_key: str | None = None,
    ) -> list[Track]:
        """Generic method to fetch paginated resources from Spotify."""
        items: list[Track] = []
        pages_count = 0

        if log_enabled:
            logger.info(f"{log_prefix} Start fetching endpoint: {endpoint}")

        while True:
            if max_pages is not None and max_pages <= pages_count:
                break

            data = await self._execute_request(
                method=method,
                endpoint=endpoint,
                params={
                    "offset": offset,
                    "limit": page_size,
                    **(params or {}),
                },
            )

            if response_key and response_key in data:
                data = data[response_key]

            try:
                page = page_model.model_validate(data)
            except ValidationError as e:
                has_local_files = any([error["type"] == LocalUnsupported for error in e.errors()])
                exc_msg = "Unsupported local files" if has_local_files else str(e)

                raise ProviderPageValidationError(
                    msg=f"{log_prefix} - Page validation error on {endpoint} (offset: {offset}): {exc_msg}",
                    code="unsupported_local_files" if has_local_files else None,
                ) from e

            items += page_processor(page, offset)
            pages_count += 1

            if log_enabled:
                logger.info(f"{log_prefix} ... processed {offset + page_size}/{page.total} ...")

            if len(items) >= page.total or len(page.items) < page_size:
                break

            offset += page_size

        return items

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        ignored_status_codes: frozenset[int] | None = None,
    ) -> dict[str, Any]:
        return await self.session_client.execute(
            method=method,
            endpoint=endpoint,
            params=params,
            json_data=json_data,
            ignored_status_codes=ignored_status_codes,
        )

    # -------------------------------------------------------------------------
    # Extractors
    # -------------------------------------------------------------------------

    def _extract_search_tracks(self, page: SpotifyPage[SpotifyTrack], *_: Any) -> list[Track]:
        return [to_domain_track(item, user_id=self.user.id) for item in page.items if item]
