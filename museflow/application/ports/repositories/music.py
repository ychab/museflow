import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Track
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackOrdering
from museflow.domain.value_objects.music import TrackKnowIdentifiers


class TrackRepository(ABC):
    """A repository for managing `Track` entities."""

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        provider_ids: list[str] | None = None,
        order: TrackOrdering | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        """Retrieves a list of tracks for a specific user.

        Args:
            user_id: The ID of the user whose tracks are to be retrieved.
            provider: A provider to filter on.
            provider_ids: Filter to only return tracks whose provider_id is in this list.
            order: Ordered list of (column, direction) tuples. Defaults to [(CREATED_AT, ASC)].
                   Use RANDOM as the sole entry for random ordering. Nullable columns
                   always sort NULLs last regardless of direction.
            offset: The number of tracks to skip before starting to collect the result set.
            limit: The maximum number of tracks to return.

        Returns:
            A list of `Track` entities.
        """
        ...

    @abstractmethod
    async def get_known_identifiers(
        self,
        user_id: uuid.UUID,
        fingerprints: list[str],
    ) -> TrackKnowIdentifiers:
        """
        Queries the database to find which of the provided fingerprints are already owned by the user.

        Args:
            user_id: The ID of the user whose known tracks are to be retrieved.
            fingerprints: A list of fingerprints to filter on

        Returns:
            A value object TrackKnowIdentifiers containing the known fingerprints.
        """
        ...

    @abstractmethod
    async def get_known_provider_ids(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        provider_ids: list[str],
    ) -> frozenset[str]:
        """Returns the subset of provider_ids already in DB for this user+provider.

        Args:
            user_id: The ID of the user to check.
            provider: The music provider to filter on.
            provider_ids: A list of provider-specific track IDs to check.

        Returns:
            A frozenset of provider_ids already present in the database.
        """
        ...

    @abstractmethod
    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[list[uuid.UUID], int]:
        """Performs a bulk "upsert" (insert or update) of track records.

        This method efficiently handles large batches of tracks, inserting new ones
        and updating existing ones based on a unique constraint (e.g., user ID + provider ID).

        Args:
            tracks: A list of `Track` entities to upsert.
            batch_size: The number of records to process in each batch.

        Returns:
            A tuple containing a list of the UUIDs of the upserted tracks and the
            total number of created rows.
        """
        ...

    @abstractmethod
    async def rate(self, user_id: uuid.UUID, track_id: uuid.UUID, score: int) -> None:
        """Persist a user rating on a track.

        Raises:
            TrackNotFoundError: If the track is not found for this user.
        """
        ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        """Deletes all tracks for a user + provider.

        Args:
            user_id: The ID of the user whose tracks are to be deleted.
            provider: A provider to filter on.

        Returns:
            The number of deleted tracks.
        """
        ...
