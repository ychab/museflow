from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class EnrichTracksConfigInput:
    force: bool = False
    batch_size: int = 200
    limit: int | None = None
