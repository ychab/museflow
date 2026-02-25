import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.music import Artist
from spotifagent.domain.entities.music import BaseMusicItem
from spotifagent.domain.entities.music import Track
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import ProviderPageValidationError
from spotifagent.domain.ports.providers.library import ProviderLibraryPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyArtist
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyPlaylist
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyPlaylistPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyPlaylistTrackPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifySavedTrackPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyTimeRange
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyTopArtistPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyTopTrackPage
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyTrack
from spotifagent.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient
from spotifagent.infrastructure.config.settings.app import app_settings

logger = logging.getLogger(__name__)


@dataclass
class SpotifyLibraryFactory:
    """Factory responsible for wiring up dependencies"""

    auth_token_repository: OAuthProviderTokenRepositoryPort
    client: SpotifyOAuthClientAdapter

    def create(self, user: User, auth_token: OAuthProviderUserToken) -> ProviderLibraryPort:
        return SpotifyLibraryAdapter(
            user=user,
            session_client=SpotifyOAuthSessionClient(
                user=user,
                auth_token=auth_token,
                auth_token_repository=self.auth_token_repository,
                client=self.client,
            ),
        )


class SpotifyLibraryAdapter(ProviderLibraryPort):
    def __init__(
        self,
        user: User,
        session_client: SpotifyOAuthSessionClient,
        max_concurrency: int = app_settings.SYNC_SEMAPHORE_MAX_CONCURRENCY,
    ) -> None:
        self.user = user
        self.session_client = session_client
        self.max_concurrency = max_concurrency

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def get_top_artists(
        self,
        page_limit: int = 50,
        time_range: SpotifyTimeRange | str | None = "long_term",
    ) -> list[Artist]:
        return await self._fetch_pages(
            endpoint="/me/top/artists",
            page_model=SpotifyTopArtistPage,
            page_processor=self._extract_top_artists,
            params={"time_range": time_range},
            limit=page_limit,
            prefix_log="[TopArtists]",
        )

    async def get_top_tracks(
        self,
        page_limit: int = 50,
        time_range: SpotifyTimeRange | str | None = "long_term",
    ) -> list[Track]:
        return await self._fetch_pages(
            endpoint="/me/top/tracks",
            page_model=SpotifyTopTrackPage,
            page_processor=self._extract_top_tracks,
            params={"time_range": time_range},
            limit=page_limit,
            prefix_log="[TopTracks]",
        )

    async def get_saved_tracks(self, page_limit: int = 50) -> list[Track]:
        return await self._fetch_pages(
            endpoint="/me/tracks",
            page_model=SpotifySavedTrackPage,
            page_processor=self._extract_saved_tracks,
            limit=page_limit,
            prefix_log="[SavedTracks]",
        )

    async def get_playlist_tracks(self, page_limit: int = 50) -> list[Track]:
        playlists = await self._fetch_pages(
            endpoint="/me/playlists",
            page_model=SpotifyPlaylistPage,
            page_processor=self._extract_playlists,
            limit=page_limit,
            prefix_log="[Playlists]",
        )
        logger.info(f"Found {len(playlists)} playlists. Fetching tracks...")

        # Use a Semaphore to limit concurrent playlist fetching to avoid rate limits and overwhelming resources.
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _fetch_with_semaphore(playlist: SpotifyPlaylist) -> list[Track]:
            async with semaphore:
                return await self._fetch_playlist_tracks(playlist, page_limit)

        # Fetch in parallel all playlist's tracks with a semaphore.
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_fetch_with_semaphore(playlist)) for playlist in playlists]

        # Gather all tracks first.
        tracks = [track for task in tasks for track in task.result()]
        # Then remove duplicates due to multiple playlists with the same tracks.
        return list({track.provider_id: track for track in tracks}.values())

    # -------------------------------------------------------------------------
    # Core Logic
    # -------------------------------------------------------------------------

    async def _fetch_playlist_tracks(self, playlist: SpotifyPlaylist, page_limit: int) -> list[Track]:
        tracks: list[Track] = []

        try:
            tracks = await self._fetch_pages(
                endpoint=f"/playlists/{playlist.id}/items",
                page_model=SpotifyPlaylistTrackPage,
                page_processor=self._extract_playlist_tracks,
                params={
                    "fields": "total,limit,offset,items(item(id,name,href,popularity,artists(id,name)))",
                    "additional_types": "track",
                },
                limit=page_limit,
                prefix_log=f"[PlaylistTracks({playlist.name})]",
            )
        except ProviderPageValidationError as e:
            # Some playlist pages can return invalid data, like missing ID's.
            # Indeed, it could happen when manually uploading custom tracks not known by Spotify.
            logger.error(f"Skip playlist {playlist.name.strip()} with error: {e}")

        return tracks

    async def _fetch_pages[SpotifyPageType: SpotifyPage, MusicItemType: BaseMusicItem | SpotifyPlaylist](
        self,
        endpoint: str,
        page_model: type[SpotifyPageType],
        page_processor: Callable[[SpotifyPageType, int], list[MusicItemType]],
        method: str = "GET",
        params: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 50,
        prefix_log: str = "",
    ) -> list[MusicItemType]:
        items: list[MusicItemType] = []

        logger.info(f"{prefix_log} Start fetching endpoint: {endpoint}")
        while True:
            data = await self._execute_request(
                method=method,
                endpoint=endpoint,
                params={
                    "offset": offset,
                    "limit": limit,
                    **(params or {}),
                },
            )

            try:
                page = page_model.model_validate(data)
            except ValidationError as e:
                raise ProviderPageValidationError(
                    f"{prefix_log} - Page validation error on {endpoint} (offset: {offset}): {e}"
                ) from e

            items += page_processor(page, offset)

            logger.info(f"{prefix_log} ... processed {offset + limit}/{page.total} ...")
            if len(items) >= page.total or len(page.items) < limit:
                break

            offset += limit

        return items

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.session_client.execute(
            method=method,
            endpoint=endpoint,
            params=params,
            json_data=json_data,
        )

    # -------------------------------------------------------------------------
    # Extractors
    # -------------------------------------------------------------------------

    def _extract_playlists(self, page: SpotifyPlaylistPage, *_: Any) -> list[SpotifyPlaylist]:
        return list(page.items)

    def _extract_top_artists(self, page: SpotifyTopArtistPage, offset: int) -> list[Artist]:
        return [self._map_top_artist(item, offset + i + 1) for i, item in enumerate(page.items)]

    def _extract_top_tracks(self, page: SpotifyTopTrackPage, offset: int) -> list[Track]:
        return [self._map_top_track(item, offset + i + 1) for i, item in enumerate(page.items)]

    def _extract_saved_tracks(self, page: SpotifySavedTrackPage, *_: Any) -> list[Track]:
        return [self._map_saved_track(item.track) for item in page.items]

    def _extract_playlist_tracks(self, page: SpotifyPlaylistTrackPage, *_: Any) -> list[Track]:
        return [self._map_track(item.item) for item in page.items if item.item]

    # -------------------------------------------------------------------------
    # Mappers (DTO)
    # -------------------------------------------------------------------------

    def _map_top_artist(self, item: SpotifyArtist, position: int) -> Artist:
        return Artist.model_validate(
            {
                **item.model_dump(exclude={"id"}),
                "provider_id": item.id,
                "user_id": self.user.id,
                "is_top": True,
                "top_position": position,
            }
        )

    def _map_top_track(self, item: SpotifyTrack, position: int) -> Track:
        return self._map_track(item, is_top=True, top_position=position)

    def _map_saved_track(self, item: SpotifyTrack) -> Track:
        return self._map_track(item, is_saved=True)

    def _map_track(self, item: SpotifyTrack, **extra_attributes: Any) -> Track:
        return Track.model_validate(
            {
                **item.model_dump(exclude={"id", "artists"}),
                "provider_id": item.id,
                "user_id": self.user.id,
                "artists": [
                    {
                        **artist.model_dump(exclude={"id"}),
                        "provider_id": artist.id,
                    }
                    for artist in item.artists
                ],
                **extra_attributes,
            }
        )
