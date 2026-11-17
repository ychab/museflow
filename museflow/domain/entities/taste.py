import uuid
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from typing import Any
from typing import Self

from museflow.domain.enums import TasteProfileStatus
from museflow.domain.utils.taste import era_sort_key
from museflow.domain.value_objects.taste import TasteProfileData


@dataclass(frozen=True, kw_only=True)
class TasteProfile:
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    name: str
    user_id: uuid.UUID

    profile: TasteProfileData

    profiler_metadata: dict[str, Any]
    tracks_count: int
    logic_version: str

    status: TasteProfileStatus = TasteProfileStatus.FINISHED

    created_at: datetime
    updated_at: datetime

    def sort_timeline(self) -> Self:
        sorted_timeline = sorted(self.profile["taste_timeline"], key=era_sort_key, reverse=True)
        sorted_profile: TasteProfileData = {**self.profile, "taste_timeline": sorted_timeline}
        return replace(self, profile=sorted_profile)
