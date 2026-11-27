import re
import uuid
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from typing import Any
from typing import Self

from museflow.domain.const import TASTE_PROFILE_NAME_PATTERN
from museflow.domain.enums import TasteProfileStatus
from museflow.domain.utils.taste import era_sort_key
from museflow.domain.value_objects.taste import TasteProfileData


@dataclass(frozen=True, kw_only=True)
class TasteProfile:
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    name: str  # the slug keying the profile, unique per user
    title: str = ""  # what the clients show, as the user typed it; the name when none was given
    user_id: uuid.UUID

    profile: TasteProfileData

    profiler_metadata: dict[str, Any]
    tracks_count: int
    logic_version: str

    status: TasteProfileStatus = TasteProfileStatus.FINISHED

    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not re.fullmatch(TASTE_PROFILE_NAME_PATTERN, self.name):
            raise ValueError(
                f"Invalid taste profile name {self.name!r}: letters, digits, '-' and '_' only, 64 at most"
            )
        if not self.title:
            object.__setattr__(self, "title", self.name)

    def sort_timeline(self) -> Self:
        sorted_timeline = sorted(self.profile["taste_timeline"], key=era_sort_key, reverse=True)
        sorted_profile: TasteProfileData = {**self.profile, "taste_timeline": sorted_timeline}
        return replace(self, profile=sorted_profile)
