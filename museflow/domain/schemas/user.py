from typing import Annotated

from pydantic import EmailStr
from pydantic import Field
from pydantic import model_validator

from museflow.domain.schemas.base import BaseEntity


class UserCreate(BaseEntity):
    """Schema for creating a new user.

    Requires an email address and a password, with password length constraints.
    """

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=100)]


class UserUpdate(BaseEntity):
    """Schema for updating an existing user.

    Allows for partial updates of a user's email or password.
    Includes validation to ensure at least one field is provided for update
    and that provided fields are not set to None.
    """

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=100)

    @model_validator(mode="after")
    def validate_payload(self):
        """Validates that at least one field is provided for update and that
        required fields are not set to None.
        """
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")

        # If those fields are set, then they cannot be None.
        protected_fields = {"email", "password"}
        for field in protected_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"The field '{field}' cannot be set to None")

        return self
