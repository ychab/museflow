import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackOrdering
from museflow.domain.types import TrackSource
from museflow.domain.value_objects.music import TrackKnowIdentifiers


class ArtistRepository(ABC):
    """A repository for managing `Artist` entities."""

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Artist]:
        """Retrieves a list of artists for a specific user.

        Args:
            user_id: The ID of the user whose artists are to be retrieved.
            provider: A provider to filter on.
            offset: The number of artists to skip before starting to collect the result set.
            limit: The maximum number of artists to return.

        Returns:
            A list of `Artist` entities.
        """
        ...

    @abstractmethod
    async def bulk_upsert(self, artists: list[Artist], batch_size: int) -> tuple[list[uuid.UUID], int]:
        """Performs a bulk "upsert" (insert or update) of artist records.

        This method efficiently handles large batches of artists, inserting new ones
        and updating existing ones based on a unique constraint (e.g., user ID + provider ID).

        Args:
            artists: A list of `Artist` entities to upsert.
            batch_size: The number of records to process in each batch.

        Returns:
            A tuple containing a list of the UUIDs of the upserted artists and the
            total number of created rows.
        """
        ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        """Deletes all artists associated with a specific user.

        Args:
            user_id: The ID of the user whose artists are to be deleted.
            provider: The music provider to filter on.

        Returns:
            The number of deleted artists.
        """
        ...


class TrackRepository(ABC):
    """A repository for managing `Track` entities."""

    @abstractmethod
    async def count(self, user_id: uuid.UUID) -> int:
        """Returns the total number of tracks for a user."""
        ...

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        sources: TrackSource | None = None,
        genres: list[str] | None = None,
        order: TrackOrdering | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        """Retrieves a list of tracks for a specific user.

        Args:
            user_id: The ID of the user whose tracks are to be retrieved.
            provider: A provider to filter on.
            sources: Whether to include, exclude, or ignore tracks base don their bitmask sources.
            genres: A list of genres to filter on.
            order: Ordered list of (column, direction) tuples. Defaults to [(CREATED_AT, ASC)].
                   Use RANDOM as the sole entry for random ordering. Nullable columns (PLAYED_AT,
                   ADDED_AT) always sort NULLs last regardless of direction.
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
        isrcs: list[str],
        fingerprints: list[str],
    ) -> TrackKnowIdentifiers:
        """
        Queries the database to find which of the provided ISRCs
        and Fingerprints are already owned by the user.

        Args:
            user_id: The ID of the user whose known tracks are to be retrieved.
            isrcs: A list of ISRC to filter on
            fingerprints: A list of fingerprints to filter on

        Returns:
            A value object TrackKnowIdentifiers containing the known ISRC and Fingerprints.
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
    async def get_distinct_genres(self, user_id: uuid.UUID, provider: MusicProvider | None = None) -> list[str]:
        """
        Returns a sorted list of all unique genres found in the user's library
        (from both tracks and their associated artists).
        """

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
    async def purge(self, user_id: uuid.UUID, provider: MusicProvider, sources: TrackSource | None = None) -> int:
        """Deletes tracks for a user based on specified criteria.

        This allows for selective deletion of tracks, for example, only removing
        tracks that are marked as "top tracks" or "saved tracks".

        Args:
            user_id: The ID of the user whose tracks are to be deleted.
            provider: A provider to filter on.
            sources: Whether to purge tracks based on their bitmask sources.

        Returns:
            The number of deleted tracks.
        """
        ...
