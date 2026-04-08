from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    name: str
    track_limit: int = 3000
    batch_size: int = 400
