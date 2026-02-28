import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy


class ArtistRepository(ABC):
    """A repository for managing `Artist` entities."""

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Artist]:
        """Retrieves a list of artists for a specific user.

        Args:
            user_id: The ID of the user whose artists are to be retrieved.
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
    async def purge(self, user_id: uuid.UUID) -> int:
        """Deletes all artists associated with a specific user.

        Args:
            user_id: The ID of the user whose artists are to be deleted.

        Returns:
            The number of deleted artists.
        """
        ...


class TrackRepository(ABC):
    """A repository for managing `Track` entities."""

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        is_top: bool | None = None,
        is_saved: bool | None = None,
        order_by: TrackOrderBy = TrackOrderBy.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        """Retrieves a list of tracks for a specific user.

        Args:
            user_id: The ID of the user whose tracks are to be retrieved.
            is_top: Whether to include, exclude, or ignore top tracks.
            is_saved: Whether to include, exclude, or ignore saved tracks.
            order_by: The column on which to order.
            sort_order: The sort order.
            offset: The number of tracks to skip before starting to collect the result set.
            limit: The maximum number of tracks to return.

        Returns:
            A list of `Track` entities.
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
    async def purge(
        self,
        user_id: uuid.UUID,
        is_top: bool = False,
        is_saved: bool = False,
        is_playlist: bool = False,
    ) -> int:
        """Deletes tracks for a user based on specified criteria.

        This allows for selective deletion of tracks, for example, only removing
        tracks that are marked as "top tracks" or "saved tracks".

        Args:
            user_id: The ID of the user whose tracks are to be deleted.
            is_top: If True, delete tracks marked as top tracks.
            is_saved: If True, delete tracks marked as saved tracks.
            is_playlist: If True, delete tracks from playlists.

        Returns:
            The number of deleted tracks.
        """
        ...
