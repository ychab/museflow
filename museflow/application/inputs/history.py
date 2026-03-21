from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImportStreamingHistoryConfigInput:
    directory: Path
    min_ms_played: int = 30_000
    batch_size: int = 300
    fetch_concurrency: int = 20
    purge: bool = False
