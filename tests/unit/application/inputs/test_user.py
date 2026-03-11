from pydantic import ValidationError

import pytest

from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput


class TestUserCreateInput:
    @pytest.mark.parametrize(
        ("length", "error_msg"),
        [
            (6, "String should have at least 8 characters"),
            (110, "String should have at most 100 characters"),
        ],
    )
    def test_password__length(self, length: int, error_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserCreateInput(email="foo@example.com", password="".join("a" for _ in range(0, length)))
        assert "1 validation error for UserCreateInput\npassword" in str(exc_info.value)
        assert error_msg in str(exc_info.value)


class TestUserUpdateInput:
    @pytest.mark.parametrize(
        ("length", "error_msg"),
        [
            (6, "String should have at least 8 characters"),
            (110, "String should have at most 100 characters"),
        ],
    )
    def test_password__length(self, length: int, error_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateInput(email="foo@example.com", password="".join("a" for _ in range(0, length)))
        assert "1 validation error for UserUpdateInput\npassword" in str(exc_info.value)
        assert error_msg in str(exc_info.value)

    def test_model_validator__one_value_set__exception(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateInput()

        assert "1 validation error for UserUpdateInput" in str(exc_info.value)
        assert "At least one field must be provided for update" in str(exc_info.value)

    @pytest.mark.parametrize("field", ["email", "password"])
    def test_model_validator__cannot_be_none(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateInput(**{field: None})

        assert "1 validation error for UserUpdateInput" in str(exc_info.value)
        assert f"The field '{field}' cannot be set to None" in str(exc_info.value)
