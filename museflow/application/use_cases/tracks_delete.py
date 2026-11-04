import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource


async def find_tracks_to_delete(
    user_id: uuid.UUID,
    artist: str | None,
    name: str | None,
    source: TrackSource | None,
    provider: MusicProvider | None,
    uow: UnitOfWorkPort,
) -> list[Track]:
    """Lists the tracks matching the filters, so the caller can confirm before passing them to `delete_tracks`."""
    async with uow:
        tracks = await uow.tracks.get_list(
            user_id=user_id,
            artist_name=artist,
            source=source,
            provider=provider,
        )

    if name is not None:
        tracks = [t for t in tracks if t.name.lower() == name.lower()]

    return tracks


async def delete_tracks(
    user_id: uuid.UUID,
    track_ids: list[uuid.UUID],
    provider: MusicProvider | None,
    uow: UnitOfWorkPort,
) -> int:
    """Deletes the given tracks; with a provider, unlinks it and deletes only the tracks left with no link."""
    async with uow:
        if provider is not None:
            orphan_ids = await uow.tracks.unlink_provider(user_id=user_id, provider=provider, track_ids=track_ids)
            return await uow.tracks.delete(user_id=user_id, track_ids=orphan_ids)

        return await uow.tracks.delete(user_id=user_id, track_ids=track_ids)
