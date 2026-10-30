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
