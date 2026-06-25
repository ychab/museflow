from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    name: str
    track_limit: int = 3000
    batch_size: int = 400
    throttling_sleep_seconds: float = 0.0
    resume: bool = False
    rated_only: bool = False
