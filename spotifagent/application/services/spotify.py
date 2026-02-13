from collections.abc import Callable
from typing import Any
from typing import Literal
from typing import TypeVar

from spotifagent.domain.entities.music import Artist
from spotifagent.domain.entities.music import BaseMusicItem
from spotifagent.domain.entities.music import Track
from spotifagent.domain.entities.spotify import SpotifyTopArtist
from spotifagent.domain.entities.spotify import SpotifyTopArtists
from spotifagent.domain.entities.spotify import SpotifyTopItem
from spotifagent.domain.entities.spotify import SpotifyTopItems
from spotifagent.domain.entities.spotify import SpotifyTopTrack
from spotifagent.domain.entities.spotify import SpotifyTopTracks
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import SpotifyAccountNotFoundError
from spotifagent.domain.ports.clients.spotify import SpotifyClientPort
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort

TimeRange = Literal["short_term", "medium_term", "long_term"]

SpotifyTopPaginatorModel = TypeVar("SpotifyTopPaginatorModel", bound=SpotifyTopItems)
SpotifyTopItemModel = TypeVar("SpotifyTopItemModel", bound=SpotifyTopItem)
MusicItemType = TypeVar("MusicItemType", bound=BaseMusicItem)


class SpotifySessionFactory:
    """
    Factory responsible for wiring up dependencies and validating
    that a user is eligible for a session.
    """

    def __init__(
        self,
        spotify_account_repository: SpotifyAccountRepositoryPort,
        spotify_client: SpotifyClientPort,
    ) -> None:
        self.spotify_account_repository = spotify_account_repository
        self.spotify_client = spotify_client

    def create(self, user: User) -> "SpotifyUserSession":
        if not user.spotify_account:
            raise SpotifyAccountNotFoundError(f"User {user.email} is not connected to Spotify.")

        return SpotifyUserSession(
            user=user,
            spotify_account_repository=self.spotify_account_repository,
            spotify_client=self.spotify_client,
        )


class SpotifyUserSession:
    """
    A service that binds a specific User to the SpotifyClient.
    It automatically handles token persistence side effects.
    """

    def __init__(
        self,
        user: User,
        spotify_account_repository: SpotifyAccountRepositoryPort,
        spotify_client: SpotifyClientPort,
    ) -> None:
        self.user = user
        self.spotify_account_repository = spotify_account_repository
        self.spotify_client = spotify_client

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response_data, token_state = await self.spotify_client.make_user_api_call(
            method=method,
            endpoint=endpoint,
            token_state=self.user.spotify_token_state,
            params=params,
            json_data=json_data,
        )

        # Check if token changed (refresh happened) and persist only if necessary
        if self.user.spotify_account and token_state.access_token != self.user.spotify_account.token_access:
            update_data = token_state.to_user_update()
            await self.spotify_account_repository.update(user_id=self.user.id, spotify_account_data=update_data)

        return response_data

    async def get_top_artists(self, limit: int = 50, time_range: TimeRange = "long_term") -> list[Artist]:
        return await self._fetch_paged_top_items(
            endpoint="/me/top/artists",
            paginator_model=SpotifyTopArtists,
            validator=self._validate_top_artist,
            limit=limit,
            time_range=time_range,
        )

    async def get_top_tracks(self, limit: int = 50, time_range: TimeRange = "long_term") -> list[Track]:
        return await self._fetch_paged_top_items(
            endpoint="/me/top/tracks",
            paginator_model=SpotifyTopTracks,
            validator=self._validate_top_track,
            limit=limit,
            time_range=time_range,
        )

    async def _fetch_paged_top_items(
        self,
        endpoint: str,
        paginator_model: type[SpotifyTopPaginatorModel],
        validator: Callable[[SpotifyTopItemModel, int], MusicItemType],
        limit: int,
        time_range: TimeRange,
    ) -> list[MusicItemType]:
        items: list[MusicItemType] = []

        offset: int = 0
        while True:
            data = await self._execute_request(
                method="GET",
                endpoint=endpoint,
                params={
                    "offset": offset,
                    "limit": limit,
                    "time_range": time_range,
                },
            )
            page = paginator_model.model_validate(data)

            items += [validator(item, offset + i + 1) for i, item in enumerate(page.items)]
            if len(items) >= page.total or len(page.items) < limit:
                break

            offset += limit

        return items

    def _validate_top_artist(self, item: SpotifyTopArtist, position: int) -> Artist:
        return Artist.model_validate(
            {
                **item.model_dump(exclude={"id"}),
                "provider_id": item.id,
                "user_id": self.user.id,
                "is_top": True,
                "top_position": position,
            }
        )

    def _validate_top_track(self, item: SpotifyTopTrack, position: int) -> Track:
        return Track.model_validate(
            {
                **item.model_dump(exclude={"id", "artists"}),
                "provider_id": item.id,
                "user_id": self.user.id,
                "is_top": True,
                "top_position": position,
                "artists": [
                    {
                        **artist.model_dump(exclude={"id"}),
                        "provider_id": artist.id,
                    }
                    for artist in item.artists
                ],
            }
        )
