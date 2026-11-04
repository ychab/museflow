import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource


class TracksDeleteUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    async def find(
        self,
        user_id: uuid.UUID,
        artist: str | None,
        name: str | None,
        source: TrackSource | None,
        provider: MusicProvider | None,
    ) -> list[Track]:
        """Lists the tracks matching the filters, so the caller can confirm before passing them to `delete`."""
        async with self._uow as uow:
            tracks = await uow.tracks.get_list(
                user_id=user_id,
                artist_name=artist,
                source=source,
                provider=provider,
            )

        if name is not None:
            tracks = [t for t in tracks if t.name.lower() == name.lower()]

        return tracks

    async def delete(self, user_id: uuid.UUID, track_ids: list[uuid.UUID], provider: MusicProvider | None) -> int:
        """Deletes the given tracks; with a provider, unlinks it and deletes only the tracks left with no link."""
        async with self._uow as uow:
            if provider is not None:
                orphan_ids = await uow.tracks.unlink_provider(user_id=user_id, provider=provider, track_ids=track_ids)
                return await uow.tracks.delete(user_id=user_id, track_ids=orphan_ids)

            return await uow.tracks.delete(user_id=user_id, track_ids=track_ids)

    async def delete_all(self, user_id: uuid.UUID) -> int:
        async with self._uow as uow:
            return await uow.tracks.delete_all(user_id=user_id)
