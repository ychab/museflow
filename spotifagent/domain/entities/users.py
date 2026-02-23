import uuid
from typing import Annotated

from pydantic import AwareDatetime
from pydantic import EmailStr
from pydantic import Field
from pydantic import model_validator

from spotifagent.domain.entities.base import BaseEntity


class User(BaseEntity):
    id: uuid.UUID
    email: EmailStr
    hashed_password: str

    is_active: bool = True

    created_at: AwareDatetime
    updated_at: AwareDatetime


class UserCreate(BaseEntity):
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=100)]


class UserUpdate(BaseEntity):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=100)

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")

        # If those fields are set, then they cannot be None.
        protected_fields = {"email", "password"}
        for field in protected_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"The field '{field}' cannot be set to None")

        return self


class UserResponse(BaseEntity):
    id: uuid.UUID
    email: EmailStr
    is_active: bool


class UserWithToken(BaseEntity):
    user: UserResponse
    access_token: str
    token_type: str = "Bearer"
