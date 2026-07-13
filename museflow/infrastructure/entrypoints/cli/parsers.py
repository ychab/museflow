from datetime import date
from typing import Annotated
from typing import get_args

from pydantic import EmailStr
from pydantic import TypeAdapter
from pydantic import ValidationError

import typer

from museflow.application.inputs.user import UserCreateInput
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locale
from museflow.infrastructure.types import LogHandler

password_field_info = UserCreateInput.model_fields["password"]

EmailAdapter = TypeAdapter(EmailStr)
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


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"Date must be in YYYY-MM-DD format, got '{value}'") from e


def parse_locale(value: str) -> LocaleCode:
    locale = validate_locale(value)
    if locale is None:
        raise typer.BadParameter(f"Locale must be a 2-letter ISO 639-1 code, got '{value}'")
    return locale


def parse_log_handlers(values: list[str]) -> list[str]:
    for value in values:
        if value not in get_args(LogHandler):
            raise typer.BadParameter(f"Invalid handler: '{values}'. Allowed: {', '.join(get_args(LogHandler))}")

    return values
