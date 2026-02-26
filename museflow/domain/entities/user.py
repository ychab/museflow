import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class User:
    id: uuid.UUID
    email: str
    hashed_password: str

    is_active: bool = True

    created_at: datetime
    updated_at: datetime
