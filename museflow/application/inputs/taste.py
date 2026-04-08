from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    name: str
    track_limit: int = 3000
    batch_size: int = 200
    throttling_sleep_seconds: float = 0.0
