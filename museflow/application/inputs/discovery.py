from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy


@dataclass(frozen=True, kw_only=True)
class DiscoveryConfigInput:
    """Configuration for the discovery process.

    Attributes:
        seed_top: Whether to use the user's top tracks as seeds.
        seed_saved: Whether to use the user's saved tracks as seeds.
        seed_genres: A list of genres to filter on the seeds.
        seed_order_by: The field to order the seed tracks by.
        seed_sort_order: The sort order for the seed tracks.
        seed_limit: The maximum number of seed tracks to use.
        similar_limit: The maximum number of similar tracks to fetch for each seed.
    """

    seed_top: bool | None = None
    seed_saved: bool | None = None
    seed_genres: list[str] = field(default_factory=list)
    seed_order_by: TrackOrderBy = TrackOrderBy.CREATED_AT
    seed_sort_order: SortOrder = SortOrder.ASC
    seed_limit: int = 50

    similar_limit: int = 5

    candidate_limit: int = 10
