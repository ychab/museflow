from typing import Annotated

from pydantic import EmailStr
from pydantic import TypeAdapter
from pydantic import ValidationError

import typer

from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate

password_field_info = UserCreate.model_fields["password"]

EmailAdapter: TypeAdapter[EmailStr] = TypeAdapter(User.model_fields["email"].annotation)
PasswordAdapter: TypeAdapter[str] = TypeAdapter(Annotated[password_field_info.annotation, password_field_info])


def parse_password(value: str) -> str:
    try:
        PasswordAdapter.validate_python(value)
    except ValidationError as e:
        raise typer.BadParameter(e.errors()[0]["msg"]) from e

    return value


def parse_email(value: str) -> str:
    try:
        EmailAdapter.validate_python(value)
    except ValidationError as e:
        raise typer.BadParameter(e.errors()[0]["msg"]) from e

    return value
