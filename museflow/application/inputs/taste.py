from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    name: str
    track_limit: int = 3000
    batch_size: int | None = None  # None: sized from the seed count
    throttling_sleep_seconds: float = 0.0
    resume: bool = False
    rated_only: bool = False
    # How long the build holds the profile without saving a checkpoint: longer than the slowest period (LLM calls,
    # their retries and the throttling sleep), or another build may take the profile over.
    lease_duration: timedelta = timedelta(minutes=15)
