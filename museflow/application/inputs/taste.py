import uuid
from dataclasses import dataclass
from datetime import timedelta

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from museflow.domain.const import TASTE_PROFILE_NAME_MAX_LENGTH
from museflow.domain.const import TASTE_PROFILE_NAME_PATTERN
from museflow.domain.utils.text import slugify


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    name: str
    title: str
    track_limit: int = 3000
    batch_size: int | None = None  # None: sized from the seed count
    throttling_sleep_seconds: float = 0.0
    resume: bool = False
    rated_only: bool = False
    # How long the build holds the profile without saving a checkpoint: longer than the slowest period (LLM calls,
    # their retries and the throttling sleep), or another build may take the profile over.
    lease_duration: timedelta = timedelta(minutes=15)
    # The job running the build, None from the CLI: a new try of the job takes over the lease its dead try left
    job_id: uuid.UUID | None = None


class BuildTasteProfileJobInput(BaseModel):
    """What a taste profile build job runs on, kept as its input.

    A Pydantic model: the API validates it as the request body, the job keeps it as JSON, read back with
    `model_validate`. Neither the seed cap nor the batch size: a try that resumes reads its periods again, which must
    match its checkpoint.
    """

    model_config = ConfigDict(frozen=True)

    title: str = Field(
        min_length=1, max_length=255, description='The profile title, as shown (e.g. "Soirées d\'hiver")'
    )
    # Optional in the body, always set once validated: empty, it is derived from the title before the pattern check
    name: str = Field(
        default="",
        validate_default=True,
        pattern=TASTE_PROFILE_NAME_PATTERN,
        description="The slug keying the profile in the URLs, unique per user. Default: the title as a slug",
    )
    rated_only: bool = Field(default=False, description="Seed the profile with the tracks the user rated only")

    @model_validator(mode="before")
    @classmethod
    def _default_name(cls, data: object) -> object:
        if isinstance(data, dict) and not data.get("name") and isinstance(data.get("title"), str):
            name = slugify(data["title"], max_length=TASTE_PROFILE_NAME_MAX_LENGTH)
            if not name:
                raise ValueError("The title needs a letter or a digit, or give a name")
            data = {**data, "name": name}

        return data
