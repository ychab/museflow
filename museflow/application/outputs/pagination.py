from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Page[T]:
    """One page of a collection: its items, and how many the whole collection holds.

    `limit` is None when the page holds the whole collection from `offset` on (the CLI lists everything).
    """

    items: list[T]
    total: int
    limit: int | None
    offset: int
