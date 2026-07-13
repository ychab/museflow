import uuid
from abc import ABC
from abc import abstractmethod
from datetime import date

from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.types import LocaleCode
from museflow.domain.types import TrackOrdering
from museflow.domain.value_objects.track import TrackKnowIdentifiers


class TrackRepository(ABC):
    """A repository for managing `Track` entities."""

    @abstractmethod
    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        provider_ids: list[str] | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        source: TrackSource | None = None,
        unrated_only: bool = False,
        exclude_skipped: bool = False,
        score_skipped_only: bool = False,
        artist_name: str | None = None,
        played_first_min: date | None = None,
        played_first_max: date | None = None,
        played_last_min: date | None = None,
        played_last_max: date | None = None,
        exclude_ids: list[uuid.UUID] | None = None,
        missing_fields: frozenset[EnrichField] | None = None,
        genres: list[GenreTag] | None = None,
        moods: list[MoodTag] | None = None,
        locales: list[LocaleCode] | None = None,
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
                   always sort NULLs last regardless of direction. Ignored when min_score is set
                   and order is not explicitly provided (falls back to score descending).
            offset: The number of tracks to skip before starting to collect the result set.
            limit: The maximum number of tracks to return.
            min_score: When set, only tracks with score >= min_score are returned. If order is
                       not explicitly provided, results are ordered by score descending so the
                       highest-rated tracks come first when limit is applied.
            max_score: When set, only tracks with score <= max_score are returned.
            source: When set, only tracks whose source bit includes this flag are returned.
            unrated_only: When True, only tracks with no score are returned.
            exclude_skipped: When True, tracks whose score_skipped is True are omitted.
            score_skipped_only: When True, only tracks whose score_skipped is True are returned.
            artist_name: When set, only tracks whose primary artist (first in the artists list)
                         matches this name (case-insensitive) are returned.
            played_first_min: When set, only tracks first played on or after this date are returned.
            played_first_max: When set, only tracks first played on or before this date are returned.
            played_last_min: When set, only tracks last played on or after this date are returned.
            played_last_max: When set, only tracks last played on or before this date are returned.
            exclude_ids: When set, tracks whose id is in this list are excluded.
            missing_fields: When set, only tracks missing at least one of the given enrichment fields are returned.
            genres: When set, only tracks whose genres array overlaps (OR) with any listed tag are returned.
            moods: When set, only tracks whose moods array overlaps (OR) with any listed tag are returned.
            locales: When set, only tracks whose locale is in this list (OR) are returned.

        Returns:
            A list of `Track` entities.
        """
        ...

    @abstractmethod
    async def get_known_identifiers(self, user_id: uuid.UUID, fingerprints: list[str]) -> TrackKnowIdentifiers:
        """
        Queries the database to find which of the provided fingerprints are already owned by the user.

        Args:
            user_id: The ID of the user whose known tracks are to be retrieved.
            fingerprints: A list of fingerprints to filter on.

        Returns:
            A value object TrackKnowIdentifiers containing the known fingerprints.
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

        Note:
            Some fields might be intentionally excluded from the ON CONFLICT DO UPDATE clause
            to protect enrichment data and user decisions from being overwritten by re-imports.
            Use :meth:`bulk_update` to write those fields explicitly.
        """
        ...

    @abstractmethod
    async def bulk_update(self, tracks: list[Track], fields: frozenset[EnrichField]) -> None:
        """Updates specific enrichment fields for a batch of existing tracks.

        Args:
            tracks: Track entities carrying the new field values (identified by ``id``).
            fields: Enrichment fields to write. Only these fields are updated; all others are left untouched.
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
    async def skip(self, user_id: uuid.UUID, track_id: uuid.UUID) -> None:
        """Permanently mark a track as unrateable.

        Sets score_skipped = True so the track is excluded from future rating queues.

        Raises:
            TrackNotFoundError: If the track is not found for this user.
        """
        ...

    @abstractmethod
    async def reset_score(self, user_id: uuid.UUID, source: TrackSource) -> int:
        """Reset scores to NULL for all tracks matching the source bit.

        Args:
            user_id: Scopes the reset to this user.
            source: Tracks whose source includes this bit will have their score cleared.

        Returns:
            The number of tracks whose score was reset.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        user_id: uuid.UUID,
        artist_name: str | None = None,
        track_name: str | None = None,
        source: TrackSource | None = None,
        provider: MusicProvider | None = None,
    ) -> int:
        """Deletes tracks matching the given filters for a user.

        All filter parameters are optional and combined with AND logic.
        At least one filter should be provided by the caller.

        Args:
            user_id: The ID of the user whose tracks are to be deleted.
            artist_name: When set, only tracks whose primary artist matches (case-insensitive) are deleted.
            track_name: When set, only tracks whose name matches (case-insensitive) are deleted.
            source: When set, only tracks whose source bit includes this flag are deleted.
            provider: When set, removes the provider link from matching tracks. Tracks with no
                      remaining provider links are fully deleted; others keep their other links.

        Returns:
            The number of fully deleted tracks.
        """
        ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        """Removes all provider links for the given provider from a user's tracks.

        Tracks whose provider_links becomes empty after removal are fully deleted.
        Tracks that still have other provider links are kept.

        Args:
            user_id: The ID of the user whose tracks are to be purged.
            provider: The provider whose links to remove.

        Returns:
            The number of fully deleted tracks.
        """
        ...
