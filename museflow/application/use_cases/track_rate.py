import uuid

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import RateScoreInvalidException


class TrackRateUseCase:
    """Rates a user's tracks one at a time: each step is its own transaction, so every answer is saved at once.

    With a provider and its library, `play` starts each track on the user's device before it is rated.
    """

    def __init__(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None,
        uow: UnitOfWorkPort,
        provider_library: ProviderLibraryPort | None = None,
    ) -> None:
        self._user_id = user_id
        self._provider = provider
        self._uow = uow
        self._provider_library = provider_library

    async def reset_scores(self, source: TrackSource) -> int:
        async with self._uow as uow:
            return await uow.tracks.reset_score(user_id=self._user_id, source=source)

    async def find_history(self, limit: int, artist: str | None) -> list[Track]:
        """Lists the unrated history tracks not skipped for good, most played first."""
        async with self._uow as uow:
            return await uow.tracks.get_list(
                user_id=self._user_id,
                source=TrackSource.HISTORY,
                unrated_only=True,
                exclude_skipped=True,
                order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
                limit=limit,
                artist_name=artist,
            )

    async def find_discovery(self, limit: int) -> list[Track]:
        """Lists the unrated discovery tracks, newest first."""
        async with self._uow as uow:
            return await uow.tracks.get_list(
                user_id=self._user_id,
                source=TrackSource.DISCOVERY,
                unrated_only=True,
                order=[(TrackOrderBy.CREATED_AT, SortOrder.DESC)],
                limit=limit,
            )

    async def find_playlist(self, playlist_id: uuid.UUID) -> list[Track]:
        """Lists every track of the playlist, rated or not.

        Raises:
            PlaylistNotFoundError: If the user has no such playlist.
        """
        async with self._uow as uow:
            playlist = await uow.playlists.get(self._user_id, playlist_id)

        if playlist is None:
            raise PlaylistNotFoundError()

        return playlist.tracks

    async def play(self, track: Track) -> None:
        """Starts the track on the user's device; does nothing for a track not linked to the provider.

        Raises:
            ProviderNoActiveDeviceException: If no device is currently active.
        """
        if self._provider is None or self._provider_library is None:
            raise ValueError("Playback needs a provider and its library")

        track_provider_id = track.get_provider_id(self._provider)
        if track_provider_id is not None:
            await self._provider_library.play_track(track_provider_id)

    async def rate(self, track_id: uuid.UUID, score: int) -> None:
        if not DISCOVERY_TRACK_SCORE_MIN <= score <= DISCOVERY_TRACK_SCORE_MAX:
            raise RateScoreInvalidException(
                f"Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, got {score}"
            )
        async with self._uow as uow:
            await uow.tracks.rate(user_id=self._user_id, track_id=track_id, score=score)

    async def skip(self, track_id: uuid.UUID) -> None:
        async with self._uow as uow:
            await uow.tracks.skip(user_id=self._user_id, track_id=track_id)

    async def blacklist_track(self, name: str, artist_name: str) -> None:
        async with self._uow as uow:
            await uow.blacklist.add_track(user_id=self._user_id, name=name, artist_name=artist_name)

    async def blacklist_artist(self, artist_name: str) -> None:
        async with self._uow as uow:
            await uow.blacklist.add_artist(user_id=self._user_id, artist_name=artist_name)
