import pytest

from museflow.infrastructure.adapters.common.llm.json_schema import MAX_ENUM_VALUES
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


class TestJsonSchemaProperty:
    def test__leaf__excludes_none_on_dump(self) -> None:
        assert JsonSchemaProperty.string().model_dump(exclude_none=True) == {"type": "string"}

    def test__string__nullable(self) -> None:
        assert JsonSchemaProperty.string(nullable=True).model_dump(exclude_none=True) == {"type": ["string", "null"]}

    def test__enum_string(self) -> None:
        assert JsonSchemaProperty.enum_string(["a", "b"]).model_dump(exclude_none=True) == {
            "type": "string",
            "enum": ["a", "b"],
        }

    def test__enum_string__nullable__any_of_null(self) -> None:
        assert JsonSchemaProperty.enum_string(["a", "b"], nullable=True).model_dump(exclude_none=True) == {
            "anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}],
        }

    def test__enum_string__max_values(self) -> None:
        values = [str(i) for i in range(MAX_ENUM_VALUES)]
        assert JsonSchemaProperty.enum_string(values).enum == values

    def test__enum_string__above_max_values(self) -> None:
        with pytest.raises(ValueError, match=f"An enum holds at most {MAX_ENUM_VALUES} values, got 101"):
            JsonSchemaProperty.enum_string([str(i) for i in range(MAX_ENUM_VALUES + 1)])

    def test__number_and_integer(self) -> None:
        assert JsonSchemaProperty.number().type == "number"
        assert JsonSchemaProperty.integer().type == "integer"

    def test__array(self) -> None:
        assert JsonSchemaProperty.array(JsonSchemaProperty.string()).model_dump(exclude_none=True) == {
            "type": "array",
            "items": {"type": "string"},
        }

    def test__object__is_strict(self) -> None:
        schema = JsonSchemaProperty.object(
            {
                "name": JsonSchemaProperty.string(),
                "nickname": JsonSchemaProperty.string(nullable=True),
            }
        )

        assert schema.model_dump(exclude_none=True) == {
            "type": "object",
            "properties": {"name": {"type": "string"}, "nickname": {"type": ["string", "null"]}},
            "required": ["name", "nickname"],
            "additionalProperties": False,
        }

    def test__object__nullable(self) -> None:
        schema = JsonSchemaProperty.object({"name": JsonSchemaProperty.string()}, nullable=True)

        assert schema.type == ["object", "null"]
        assert schema.required == ["name"]
        assert schema.additionalProperties is False
