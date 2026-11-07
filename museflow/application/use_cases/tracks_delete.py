import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource


class DeleteTracksUseCase:
    """Deletes a user's tracks; with a provider, every step only targets that provider's tracks and unlinks it.

    A track still linked to another provider is kept; only the tracks left with no link are deleted.
    """

    def __init__(self, user_id: uuid.UUID, provider: MusicProvider | None, uow: UnitOfWorkPort) -> None:
        self._user_id = user_id
        self._provider = provider
        self._uow = uow

    async def find(self, artist: str | None, name: str | None, source: TrackSource | None) -> list[Track]:
        """Lists the tracks matching the filters, so the caller can confirm before passing them to `delete`."""
        async with self._uow as uow:
            tracks = await uow.tracks.list(
                user_id=self._user_id,
                artist_name=artist,
                source=source,
                provider=self._provider,
            )

        if name is not None:
            tracks = [t for t in tracks if t.name.lower() == name.lower()]

        return tracks

    async def delete(self, track_ids: list[uuid.UUID]) -> int:
        async with self._uow as uow:
            if self._provider is not None:
                orphan_ids = await uow.tracks.unlink_provider(
                    user_id=self._user_id,
                    provider=self._provider,
                    track_ids=track_ids,
                )
                return await uow.tracks.delete(user_id=self._user_id, track_ids=orphan_ids)

            return await uow.tracks.delete(user_id=self._user_id, track_ids=track_ids)

    async def delete_all(self) -> int:
        async with self._uow as uow:
            if self._provider is not None:
                orphan_ids = await uow.tracks.unlink_provider(user_id=self._user_id, provider=self._provider)
                return await uow.tracks.delete(user_id=self._user_id, track_ids=orphan_ids)

            return await uow.tracks.purge(user_id=self._user_id)
