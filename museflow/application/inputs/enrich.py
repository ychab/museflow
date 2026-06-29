from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True, kw_only=True)
class EnrichTracksConfigInput:
    force: bool = False
    batch_size: int = 200
    limit: int | None = None


class EnrichEntryInput(BaseModel):
    fingerprint: str
    genres: list[str] = []
    moods: list[str] = []
